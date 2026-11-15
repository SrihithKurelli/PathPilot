"""Two parallel paths between h1 and h2."""
import argparse
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def build_network(controller_ip="127.0.0.1",controller_port=6653):
    net=Mininet(controller=None,switch=OVSSwitch,link=TCLink,build=False,autoSetMacs=True)
    h1=net.addHost("h1",ip="10.0.0.1/24"); h2=net.addHost("h2",ip="10.0.0.2/24")
    s1=net.addSwitch("s1",protocols="OpenFlow13"); s2=net.addSwitch("s2",protocols="OpenFlow13")
    s3=net.addSwitch("s3",protocols="OpenFlow13"); s4=net.addSwitch("s4",protocols="OpenFlow13")
    net.addLink(h1,s1,cls=TCLink,bw=100,delay="1ms")
    net.addLink(s1,s2,cls=TCLink,bw=100,delay="2ms")
    net.addLink(s1,s3,cls=TCLink,bw=100,delay="2ms")
    net.addLink(s2,s4,cls=TCLink,bw=100,delay="2ms")
    net.addLink(s3,s4,cls=TCLink,bw=100,delay="2ms")
    net.addLink(s4,h2,cls=TCLink,bw=100,delay="1ms")
    c0=net.addController("c0",controller=RemoteController,ip=controller_ip,port=controller_port)
    net.build()
    for sw in (s1,s2,s3,s4): sw.start([c0])
    return net
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--controller",default="127.0.0.1"); ap.add_argument("--port",type=int,default=6653); a=ap.parse_args()
    setLogLevel("info"); net=build_network(a.controller,a.port)
    try: info("*** PathPilot topology ready\n"); CLI(net)
    finally: net.stop()
if __name__=="__main__": main()
