"""Ryu OpenFlow 1.3 controller for the PathPilot two-path teaching topology."""
import hashlib
import json
import os
import random
import time
from pathlib import Path

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    DEAD_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls,
)
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, ipv4, tcp, udp
from ryu.lib.packet import ether_types
from ryu.ofproto import ofproto_v1_3

from controller.live_telemetry import PortRateTracker
from controller.policies import Telemetry, choose_path
from experiments.path_pinning import pinned_experiment_path


class PathPilotController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    PATH_PORTS = {"s1-s2-s4": 2, "s1-s3-s4": 3}
    STATS_INTERVAL_S = 2.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy = os.getenv("PATHPILOT_POLICY", "least_loaded")
        self.telemetry_file = Path(
            os.getenv("PATHPILOT_TELEMETRY", "experiments/telemetry.json")
        )
        self.telemetry_delay_s = float(
            os.getenv("PATHPILOT_TELEMETRY_DELAY_S", "0")
        )
        self.telemetry_noise_std = float(
            os.getenv("PATHPILOT_TELEMETRY_NOISE_STD", "0")
        )
        if self.telemetry_delay_s < 0:
            raise ValueError("PATHPILOT_TELEMETRY_DELAY_S must be non-negative")
        if not 0 <= self.telemetry_noise_std <= 1:
            raise ValueError("PATHPILOT_TELEMETRY_NOISE_STD must be in [0,1]")
        self.telemetry_rng = random.Random(
            int(os.getenv("PATHPILOT_TELEMETRY_SEED", "7"))
        )
        self.experiment_initial_path = os.getenv("PATHPILOT_EXPERIMENT_INITIAL_PATH")
        self.experiment_first_flow_port = int(
            os.getenv("PATHPILOT_EXPERIMENT_FIRST_FLOW_PORT", "5001")
        )
        # The optional pin is restricted to the designated first-flow TCP port.
        pinned_experiment_path(
            self.experiment_initial_path, self.experiment_first_flow_port,
            self.experiment_first_flow_port,
        )
        self.reverse_paths = {}
        self.last_selected_path = None
        self.datapaths = {}
        self.port_rate_tracker = PortRateTracker()
        self._stats_reply_switches = set()
        self._logged_live_ready = False
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
            self.port_rate_tracker.reset_datapath(dp.id)
            self._stats_reply_switches.discard(dp.id)
            self._logged_live_ready = False
            self.logger.info("Switch %s connected; port polling enabled", dp.id)
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)
            self.port_rate_tracker.reset_datapath(dp.id)
            self._stats_reply_switches.discard(dp.id)
            self._logged_live_ready = False
            self.logger.info("Switch %s disconnected", dp.id)

    def _monitor(self):
        while True:
            for dp in list(self.datapaths.values()):
                parser = dp.ofproto_parser
                request = parser.OFPPortStatsRequest(
                    dp, 0, dp.ofproto.OFPP_ANY
                )
                try:
                    dp.send_msg(request)
                except Exception as exc:
                    self.logger.debug(
                        "Could not request port stats from switch %s: %s",
                        dp.id, exc,
                    )
            hub.sleep(self.STATS_INTERVAL_S)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply(self, ev):
        now = time.monotonic()
        dpid = ev.msg.datapath.id
        for stat in ev.msg.body:
            self.port_rate_tracker.update_port(
                dpid, stat.port_no, stat.tx_bytes, now
            )
        if dpid not in self._stats_reply_switches:
            self._stats_reply_switches.add(dpid)
            self.logger.info("Received first port-stats reply from switch %s", dpid)
        live = self.port_rate_tracker.path_telemetry(now)
        if live is not None and not self._logged_live_ready:
            self._logged_live_ready = True
            self.logger.info(
                "Live telemetry ready: s1-s2-s4 utilization=%.4f, "
                "s1-s3-s4 utilization=%.4f",
                live["s1-s2-s4"].utilization,
                live["s1-s3-s4"].utilization,
            )

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp = ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        actions = [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)]
        dp.send_msg(p.OFPFlowMod(
            datapath=dp,
            priority=0,
            match=p.OFPMatch(),
            instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)],
        ))

    def _impair_telemetry(self, telemetry):
        if self.telemetry_noise_std == 0:
            return telemetry
        impaired = {}
        for path, sample in telemetry.items():
            noisy_utilization = min(
                1.0,
                max(0.0, sample.utilization
                    + self.telemetry_rng.gauss(0, self.telemetry_noise_std)),
            )
            # The configured noise scale is exposed as uncertainty metadata;
            # the uncertainty-aware policy can then discount noisy samples.
            impaired[path] = Telemetry(
                utilization=noisy_utilization,
                age_s=sample.age_s,
                variability=max(sample.variability, self.telemetry_noise_std),
            )
        return impaired

    def read_telemetry(self):
        # Select a genuinely historical OpenFlow sample when delay is enabled.
        live = self.port_rate_tracker.path_telemetry(
            time.monotonic(),
            delay_s=self.telemetry_delay_s,
            max_age_s=self.port_rate_tracker.max_age_s + self.telemetry_delay_s,
        )
        if live is not None:
            live = self._impair_telemetry(live)
            self.logger.info(
                "Using LIVE telemetry: s1-s2-s4=%.4f (age %.1fs), "
                "s1-s3-s4=%.4f (age %.1fs), delay=%.1fs noise_std=%.3f",
                live["s1-s2-s4"].utilization,
                live["s1-s2-s4"].age_s,
                live["s1-s3-s4"].utilization,
                live["s1-s3-s4"].age_s,
                self.telemetry_delay_s,
                self.telemetry_noise_std,
            )
            return live

        try:
            raw = json.loads(self.telemetry_file.read_text())
            telemetry = {key: Telemetry(**value) for key, value in raw.items()}
            self.logger.info("Using STATIC telemetry fallback from %s", self.telemetry_file)
            return telemetry
        except (OSError, ValueError, TypeError) as exc:
            self.logger.warning(
                "Telemetry unavailable (%s); using conservative fallback", exc
            )
            return {
                "s1-s2-s4": Telemetry(.5, 999, 1),
                "s1-s3-s4": Telemetry(.5, 999, 1),
            }

    @staticmethod
    def flow_key(ip, transport):
        proto = ip.proto
        if transport is None:
            src_port = dst_port = 0
        else:
            src_port, dst_port = transport.src_port, transport.dst_port
        return (ip.src, ip.dst, proto, src_port, dst_port)

    @staticmethod
    def reverse_key(key):
        src, dst, proto, src_port, dst_port = key
        return (dst, src, proto, dst_port, src_port)

    def install(self, dp, match, out_port):
        p, o = dp.ofproto_parser, dp.ofproto
        dp.send_msg(p.OFPFlowMod(
            datapath=dp,
            priority=100,
            match=match,
            idle_timeout=60,
            instructions=[p.OFPInstructionActions(
                o.OFPIT_APPLY_ACTIONS, [p.OFPActionOutput(out_port)]
            )],
        ))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg, dp = ev.msg, ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype != ether_types.ETH_TYPE_IP:
            return
        ip = pkt.get_protocol(ipv4.ipv4)
        if ip is None:
            return
        tcp_pkt, udp_pkt = pkt.get_protocol(tcp.tcp), pkt.get_protocol(udp.udp)
        transport = tcp_pkt or udp_pkt
        if ip.proto not in (1, 6, 17):
            return

        in_port = msg.match["in_port"]
        key = self.flow_key(ip, transport)
        if dp.id == 1:
            if in_port == 1:
                pinned_path = pinned_experiment_path(
                    self.experiment_initial_path,
                    tcp_pkt.dst_port if tcp_pkt else None,
                    self.experiment_first_flow_port,
                )
                if pinned_path is not None:
                    # Reset any path state created by the connectivity ping; the
                    # priming flow must not bias the policy's second decision.
                    self.last_selected_path = None
                    path = pinned_path
                    self.logger.info(
                        "Experiment path pin applied to TCP destination port %s: %s",
                        tcp_pkt.dst_port, path,
                    )
                else:
                    telemetry = self.read_telemetry()
                    # When uncertainty-aware telemetry cannot distinguish
                    # paths, avoid a permanent alphabetical bias. A stable
                    # hash of the flow 5-tuple gives a reproducible fallback
                    # distributed across new flows without random state.
                    safe_fallback = self.last_selected_path
                    if self.policy == "uncertainty_aware" and safe_fallback is None:
                        candidates = sorted(telemetry)
                        digest = hashlib.sha256(repr(key).encode("utf-8")).digest()
                        safe_fallback = candidates[
                            int.from_bytes(digest[:8], "big") % len(candidates)
                        ]
                    path = choose_path(
                        telemetry,
                        self.policy,
                        previous_path=self.last_selected_path,
                        safe_fallback=safe_fallback,
                    )
                    self.last_selected_path = path
                self.logger.info(
                    "Selected path %s for new flow %s -> %s (policy=%s)",
                    path, ip.src, ip.dst, self.policy,
                )
                self.reverse_paths[self.reverse_key(key)] = path
                out_port = self.PATH_PORTS[path]
            else:
                out_port = 1
        elif dp.id in (2, 3):
            out_port = 2 if in_port == 1 else 1
        elif dp.id == 4:
            if in_port in (1, 2):
                out_port = 3
            elif in_port == 3:
                path = self.reverse_paths.get(key, "s1-s2-s4")
                out_port = 1 if path == "s1-s2-s4" else 2
            else:
                return
        else:
            return

        fields = {
            "eth_type": ether_types.ETH_TYPE_IP,
            "ipv4_src": ip.src,
            "ipv4_dst": ip.dst,
            "ip_proto": ip.proto,
        }
        if tcp_pkt:
            fields.update({"tcp_src": tcp_pkt.src_port, "tcp_dst": tcp_pkt.dst_port})
        elif udp_pkt:
            fields.update({"udp_src": udp_pkt.src_port, "udp_dst": udp_pkt.dst_port})
        match = p.OFPMatch(**fields)
        self.install(dp, match, out_port)
        data = None if msg.buffer_id != o.OFP_NO_BUFFER else msg.data
        dp.send_msg(p.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=[p.OFPActionOutput(out_port)],
            data=data,
        ))
