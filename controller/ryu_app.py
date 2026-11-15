"""Ryu OpenFlow 1.3 controller for the PathPilot two-path teaching topology.

The controller samples OpenFlow port counters, selects a path for each new
IPv4 flow, and pins the reverse direction to the same path. Existing flows
are not migrated.
"""
import json
import os
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
        self.reverse_paths = {}
        self.datapaths = {}
        self.port_rate_tracker = PortRateTracker()
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, ev):
        dp = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp
            self.port_rate_tracker.reset_datapath(dp.id)
            self.logger.info("Switch %s connected; port polling enabled", dp.id)
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)
            self.port_rate_tracker.reset_datapath(dp.id)
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

    def read_telemetry(self):
        # Prefer fresh switch measurements. Static JSON remains a startup and
        # stale-data fallback until both candidate paths have fresh samples.
        live = self.port_rate_tracker.path_telemetry(time.monotonic())
        if live is not None:
            return live

        try:
            raw = json.loads(self.telemetry_file.read_text())
            return {key: Telemetry(**value) for key, value in raw.items()}
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
        # TCP, UDP, and ICMP are supported in this starter.
        if ip.proto not in (1, 6, 17):
            return

        in_port = msg.match["in_port"]
        key = self.flow_key(ip, transport)
        if dp.id == 1:
            if in_port == 1:  # New flow from h1
                path = choose_path(
                    self.read_telemetry(),
                    self.policy,
                    safe_fallback="s1-s2-s4",
                )
                self.reverse_paths[self.reverse_key(key)] = path
                out_port = self.PATH_PORTS[path]
            else:  # Return traffic from either middle switch to h1
                out_port = 1
        elif dp.id in (2, 3):
            # Each middle switch has port 1 toward s1 and port 2 toward s4.
            out_port = 2 if in_port == 1 else 1
        elif dp.id == 4:
            if in_port in (1, 2):  # Forward traffic toward h2
                out_port = 3
            elif in_port == 3:  # Reply from h2: pin to the original path
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
            fields.update({
                "tcp_src": tcp_pkt.src_port,
                "tcp_dst": tcp_pkt.dst_port,
            })
        elif udp_pkt:
            fields.update({
                "udp_src": udp_pkt.src_port,
                "udp_dst": udp_pkt.dst_port,
            })
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
