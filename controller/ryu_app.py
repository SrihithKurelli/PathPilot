"""Ryu OpenFlow 1.3 starter: assigns new IPv4 TCP/UDP flows to one of two paths."""
import json, os
from pathlib import Path
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, tcp, udp
from ryu.lib.packet import ether_types
from controller.policies import Telemetry, choose_path

class PathPilotController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    # Port numbers follow topology/mininet_topology.py.
    PATHS = {"s1-s2-s4": 2, "s1-s3-s4": 3}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy = os.getenv("PATHPILOT_POLICY", "least_loaded")
        self.telemetry_file = Path(os.getenv("PATHPILOT_TELEMETRY", "experiments/telemetry.json"))
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):
        dp=ev.msg.datapath; p=dp.ofproto_parser; o=dp.ofproto
        actions=[p.OFPActionOutput(o.OFPP_CONTROLLER,o.OFPCML_NO_BUFFER)]
        dp.send_msg(p.OFPFlowMod(datapath=dp,priority=0,match=p.OFPMatch(),
            instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,actions)]))
    def read_telemetry(self):
        try:
            raw=json.loads(self.telemetry_file.read_text())
            return {k:Telemetry(**v) for k,v in raw.items()}
        except (OSError,ValueError,TypeError) as exc:
            self.logger.warning("Telemetry unavailable (%s); using fallback snapshot",exc)
            return {"s1-s2-s4":Telemetry(.5,999,1),"s1-s3-s4":Telemetry(.5,999,1)}
    def install(self,dp,match,port):
        p=dp.ofproto_parser;o=dp.ofproto
        dp.send_msg(p.OFPFlowMod(datapath=dp,priority=100,match=match,idle_timeout=30,
            instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS,[p.OFPActionOutput(port)])]))
    @set_ev_cls(ofp_event.EventOFPPacketIn,MAIN_DISPATCHER)
    def packet_in(self,ev):
        msg=ev.msg;dp=msg.datapath;p=dp.ofproto_parser;o=dp.ofproto
        pkt=packet.Packet(msg.data); eth=pkt.get_protocol(ethernet.ethernet)
        if eth is None or eth.ethertype==ether_types.ETH_TYPE_LLDP:return
        ip=pkt.get_protocol(ipv4.ipv4)
        if ip is None:return
        t=pkt.get_protocol(tcp.tcp); u=pkt.get_protocol(udp.udp); transport=t or u
        if transport is None:return
        # This initial data plane is intentionally limited to the linear two-host topology.
        if dp.id==1:
            selected=choose_path(self.read_telemetry(),self.policy,safe_fallback="s1-s2-s4")
            out=self.PATHS[selected]
        elif dp.id in (2,3): out=2
        elif dp.id==4: out=3
        else:return
        fields={"eth_type":ether_types.ETH_TYPE_IP,"ipv4_src":ip.src,"ipv4_dst":ip.dst,"ip_proto":ip.proto}
        fields.update({"tcp_src":transport.src_port,"tcp_dst":transport.dst_port} if t else {"udp_src":transport.src_port,"udp_dst":transport.dst_port})
        match=p.OFPMatch(**fields); self.install(dp,match,out)
        data=None if msg.buffer_id!=o.OFP_NO_BUFFER else msg.data
        dp.send_msg(p.OFPPacketOut(datapath=dp,buffer_id=msg.buffer_id,in_port=msg.match["in_port"],
            actions=[p.OFPActionOutput(out)],data=data))
