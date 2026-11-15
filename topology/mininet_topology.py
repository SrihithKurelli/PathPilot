"""Two parallel paths between h1 and h2."""
import argparse
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def build_network(controller_ip="127.0.0.1", controller_port=6653):
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, build=False, autoSetMacs=True)
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    s2 = net.addSwitch("s2", protocols="OpenFlow13")
    s3 = net.addSwitch("s3", protocols="OpenFlow13")
    s4 = net.addSwitch("s4", protocols="OpenFlow13")

    # Port map: s1(h1=1,s2=2,s3=3); s2(s1=1,s4=2);
    # s3(s1=1,s4=2); s4(s2=1,s3=2,h2=3).
    net.addLink(h1, s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(s1, s2, cls=TCLink, bw=100, delay="2ms")
    net.addLink(s1, s3, cls=TCLink, bw=100, delay="2ms")
    net.addLink(s2, s4, cls=TCLink, bw=100, delay="2ms")
    net.addLink(s3, s4, cls=TCLink, bw=100, delay="2ms")
    net.addLink(s4, h2, cls=TCLink, bw=100, delay="1ms")

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
