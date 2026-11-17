"""Two parallel paths between h1 and h2."""
import argparse
import os
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def build_network(controller_ip="127.0.0.1", controller_port=6653):
    link_bw_mbps = float(os.getenv("PATHPILOT_LINK_BW_MBPS", "100"))
    access_delay_ms = float(os.getenv("PATHPILOT_ACCESS_DELAY_MS", "1"))
    interswitch_delay_ms = float(os.getenv("PATHPILOT_INTERSWITCH_DELAY_MS", "2"))
    if link_bw_mbps <= 0 or access_delay_ms < 0 or interswitch_delay_ms < 0:
        raise ValueError("link bandwidth must be positive and delays non-negative")
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, build=False, autoSetMacs=True)
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    s1 = net.addSwitch("s1", dpid="0000000000000001", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", dpid="0000000000000002", protocols="OpenFlow13")
    s3 = net.addSwitch("s3", dpid="0000000000000003", protocols="OpenFlow13")
    s4 = net.addSwitch("s4", dpid="0000000000000004", protocols="OpenFlow13")

    # Port map: s1(h1=1,s2=2,s3=3); s2(s1=1,s4=2);
    # s3(s1=1,s4=2); s4(s2=1,s3=2,h2=3).
    access_delay = f"{access_delay_ms}ms"
    interswitch_delay = f"{interswitch_delay_ms}ms"
    net.addLink(h1, s1, cls=TCLink, bw=link_bw_mbps, delay=access_delay)
    net.addLink(s1, s2, cls=TCLink, bw=link_bw_mbps, delay=interswitch_delay)
    net.addLink(s1, s3, cls=TCLink, bw=link_bw_mbps, delay=interswitch_delay)
    net.addLink(s2, s4, cls=TCLink, bw=link_bw_mbps, delay=interswitch_delay)
    net.addLink(s3, s4, cls=TCLink, bw=link_bw_mbps, delay=interswitch_delay)
    net.addLink(s4, h2, cls=TCLink, bw=link_bw_mbps, delay=access_delay)

    c0 = net.addController("c0", controller=RemoteController, ip=controller_ip, port=controller_port)
    net.build()
    for sw in (s1, s2, s3, s4):
        sw.start([c0])
    # Avoid ARP flooding loops across the parallel paths in this starter topology.
    net.staticArp()
    return net

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--controller", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=6653)
    args = ap.parse_args()
    setLogLevel("info")
    net = build_network(args.controller, args.port)
    try:
        info("*** PathPilot topology ready\\n")
        CLI(net)
    finally:
        net.stop()

if __name__ == "__main__":
    main()
