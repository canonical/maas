> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/a-primer-on-tcp-ip" target = "_blank">Let us know.</a>*

Understanding networking fundamentals is essential for designing, operating, and troubleshooting MAAS networks. TCP/IP networking can seem complex at first, but by breaking it down into layers and core concepts, we can gain a solid understanding of how it works.  For a very long time, there were at least as many network protocols as there were brands and styles of computers. Different methods were needed to share information from one system to another, sometimes even involving specially-crafted physical interface cables to handle the translation. Eventually, though, computer networks began to gravitate toward a standard approach, known as TCP/IP.

### POTS

The history of the internet traces back to the mid-20th century, when computer networking began to take shape. Its origins are closely intertwined with the Plain Old Telephone System (POTS) -- the traditional landline telephone network -- which served as the communications infrastructure before the internet era. Initially relying on circuit-switched networks, POTS faced limitations in data transmission, leading to the birth of packet-switched networks that formed the foundation of the internet.

In the 1960s, the U.S. Department of Defence Advanced Research Projects Agency (ARPA) pioneered a decentralised communication network, resulting in the creation of ARPANET in 1969. ARPANET utilised packet-switching technology to transmit data packets across interconnected computers. As ARPANET expanded, the need for standardised protocols emerged, leading to the development of the Transmission Control Protocol/Internet Protocol (TCP/IP) in the 1970s. TCP/IP established a common language for diverse computer systems to communicate and laid the groundwork for the modern internet.

Later on, the internet evolved and became more accessible. The emergence of commercial ISPs in the 1990s brought internet access to the general public, while the World Wide Web introduced a user-friendly interface for browsing and accessing information. Today, the internet connects billions of devices globally, facilitating communication, information sharing, e-commerce, and more. The transformation of POTS from circuit-switched to packet-switched networks played a pivotal role in paving the way for the creation of the internet, revolutionising our modern digital landscape.

## The OSI model explained

The OSI (Open Systems Interconnection) model provides a conceptual framework for network communication by dividing it into 7 layers:

- Physical - Transmits raw bit streams over a physical medium. Concerned with voltages, frequencies, cable types, connector pins, etc.
- Data Link - Provides node-to-node data transfer across a network medium. Handles MAC addressing, framing, error checking, and flow control.
- Network - Handles logical addressing and routing of data packets over multiple networks. IP and routing protocols like ARP operate here.
- Transport - Manages end-to-end transmission and integrity of data. TCP and UDP operate at this layer.
- Session - Establishes, maintains, and terminates sessions between local and remote applications. Handles session multiplexing.
- Presentation - Formats and encrypts data for the application layer. Deals with syntax and semantics.
- Application - Provides network services directly to end user applications. HTTP, FTP, SMTP etc. operate at this layer.

This standardised model promotes modular design and interoperability between diverse systems. Developed in the late 1970s, it consists of seven layers, namely: Physical, Data Link, Network, Transport, Session, Presentation, and Application. The bottom three layers (Physical, Data Link, and Network) handle data transmission and routing. The Physical layer manages the physical transmission of bits over a medium. The Data Link layer ensures reliable data frame transmission between directly connected devices. The Network layer handles addressing, routing, and logical organisation across networks.

The Transport layer focuses on end-to-end data delivery, dividing data into segments and ensuring reliable transport between source and destination. It manages error recovery and flow control. The top three layers (Session, Presentation, and Application) are responsible for user interactions and application-specific functions. The Session layer establishes, maintains, and terminates communication sessions. The Presentation layer handles data formatting, encryption, and compression. The Application layer provides access to network services such as email, web browsing, and file transfer.

While real-world protocols may not strictly adhere to the OSI model, it help a lot in understanding network communication by breaking it down into discrete layers. The model promotes standardisation, modularity, and interoperability in networking protocols, facilitating troubleshooting and development.

### Enough talk, let's do something

Here's a `ping` exercise that demonstrates the network layer functionality in the OSI model:

1. Open the command prompt or terminal (hint: on Ubuntu, press `Ctrl + Alt + T` -- this works even if you're running Emacs!):

2. Type "ping www.google.com" and press `Enter`; `ping` is used to test connectivity and measure the round-trip time (RTT) between your computer and a remote host. By specifying "www.google.com" as the destination, you are pinging Google's server.

3. Observe the output, which will display information about the ICMP packets sent and received. Each line represents a round-trip time (RTT) measurement. `ping` sends ICMP *Echo Request* packets to the destination, and if the remote server is reachable, it responds with ICMP *Echo Reply* packets.  The output will show the RTT in milliseconds (ms) for each packet sent and received, along with statistics about packet loss and round-trip times, something like this:

```nohighlight
Pinging www.google.com [172.217.169.132] with 32 bytes of data:
Reply from 172.217.169.132: bytes=32 time=13ms TTL=56
Reply from 172.217.169.132: bytes=32 time=12ms TTL=56
Reply from 172.217.169.132: bytes=32 time=14ms TTL=56
Reply from 172.217.169.132: bytes=32 time=11ms TTL=56

Ping statistics for 172.217.169.132:
    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Approximate round trip times in milliseconds:
    Minimum = 11ms, Maximum = 14ms, Average = 12ms
```

#### What you just did

- `ping` operates at the Network layer (Layer 3) of the OSI model. It uses ICMP (Internet Control Message Protocol) packets to test connectivity and measure the RTT between your computer and the destination host.
- When you execute the command, your computer constructs an ICMP Echo Request packet and sends it to the destination (in this case, www.google.com).
- If the destination host is reachable and not blocking ICMP traffic, it will respond with an ICMP Echo Reply packet, indicating that the destination is reachable.
- The output displays information about the packets sent and received, including the RTT, TTL (Time-to-Live), and packet size.
- The statistics section at the end provides a summary of the ping session, including the number of packets sent, received, and lost, as well as the minimum, maximum, and average RTT.

By using the "ping" command, you can verify network connectivity, diagnose network issues, and measure the latency between your computer and a remote host, showcasing the functionality of the Network layer in the OSI model.

### Let's go up a few levels

Let's access a chess server, in the terminal, using ASCII:

1. Open the command prompt or terminal.

2. Type "telnet freechess.org 5000" and press Enter.

3. Watch as you receive a login prompt for an online, ASCII chess server.

#### What you just did

The "telnet" command establishes a Telnet session with the specified host (freechess.org in this case) at a specific port (5000, in this case). Telnet is an *application layer* protocol that allows you to remotely access and control another computer or device. This exercise demonstrates how applications can use the Application layer (Layer 7) of the OSI model to provide specific services.

### The Physical layer (Layer 1)

1. Open the terminal: Press Ctrl + Alt + T to open the terminal.

2. Use the ip command to gather information about network interfaces:

```nohighlight
ip link show
```

#### What you just did

In networking, Layer 1 refers to the Physical layer of the OSI model. It is the lowest layer and deals with the physical transmission of data. Layer 1 interfaces provide the means to connect devices to a network and transfer data in the form of electrical, optical, or radio signals. This command `ip link show` displays a list of network interfaces -- links -- on your system along with their state, MAC address, and other details. Each network interface -- each "link" -- operates at the Physical layer (Layer 1) of the OSI model.

Here are some more relevant details on the links you might find at this level:

1. **Network Interface Card (NIC)**: A Network Interface Card, commonly known as a NIC or network adaptor, is a hardware component that allows a device to connect to a network. It can be an Ethernet card, Wi-Fi card, or other types of interface.  The NIC is responsible for converting data from the device into a format suitable for transmission over the network medium, such as electrical signals for wired connections or radio waves for wireless connections. Examples of NICs include Ethernet cards for wired connections or Wi-Fi cards for wireless connections.

2. **Ethernet Cable**: Ethernet cables are used for wired network connections and are commonly used in home and office environments.  They consist of copper wires inside an insulated casing and come in different categories such as Cat 5, Cat 6, or Cat 7, offering varying levels of performance.  Ethernet cables connect devices, such as computers or routers, to Ethernet ports on NICs, switches, or routers, enabling the transmission of data at high speeds.

3. **Fibre Optic Cable**:  Fibre optic cables use thin strands of glass or plastic to transmit data as pulses of light.  They offer high-speed and long-distance data transmission capabilities, making them ideal for high-bandwidth applications or for connecting geographically distant locations.  Fibre optic cables are used in various networking environments, including telecommunications networks, data centres, and high-speed internet connections.

4. **Wireless Interfaces**: Wireless interfaces, such as Wi-Fi or Bluetooth, enable wireless communication between devices.  Wi-Fi interfaces use radio waves to transmit data over the air, allowing devices to connect to a wireless network and access the internet or communicate with other devices.  Bluetooth interfaces are used for short-range wireless connections between devices, such as connecting a smartphone to a wireless headset or a laptop to a wireless mouse.

5. **Network Connectors**: Network connectors are physical connectors that join network cables to networking devices or interfaces. Common network connectors include RJ-45 connectors for Ethernet cables, which are commonly used for wired connections, and various connectors such as LC or SC connectors for fibre optic cables.  These connectors ensure a secure and reliable connection between the cable and the networking device.

Layer 1 interfaces, such as NICs, cables, and connectors, play a crucial role in establishing the physical connectivity required for network communication. They handle the transmission of signals, whether electrical, optical, or radio waves, to ensure that data can be sent and received across the network. Understanding Layer 1 interfaces is fundamental in comprehending how devices connect and interact within a network infrastructure.

### The Data Link layer (Layer 2)

Let's explore the Data Link layer -- Layer 2 -- which is the next layer up.

#### MAC addresses

Run the following command:

```nohighlight
ifconfig
```

#### What you just did

Running the ifconfig command on Linux/macOS or ipconfig on Windows will display the network interface configuration, including the MAC (Media Access Control) address of each interface.  You may see the MAC address labelled as `ether`.  The MAC address, also known as the hardware address, is a unique identifier assigned to the network interface card (NIC) at the Data Link layer (Layer 2) of the OSI model.  

By "unique", we mean that no other Internet-facing device has the same address, so network devices can find that MAC address in exactly one place in the world.  For example, when someone puts your unique street address, city, state, and zip code on a letter, it means that (theoretically) it should only be delivered to one mailbox in the world.  By examining the MAC addresses, you can identify the devices or interfaces on the local network, but by their global addresses.

You might notice that the `lo` (loopback) address doesn't have a MAC address.  This is because the loopback is an internal connection that never ventures onto the internet.  Think of this like telling someone that "the mail is on the kitchen table" -- it works fine if you're in your own house, but it would only cause confusion if you used "kitchen table" in the outside world.

#### arp

Type the following command (on Ubuntu):

```nohighlight
arp -n
```

You'll probably get an output something like this:

```nohighlight
$ arp -n
Address                  HWtype  HWaddress           Flags Mask            Iface
10.156.28.2              ether   00:16:3e:f6:8b:90   C                     lxdbr0
192.168.1.1              ether   d0:76:8f:e6:94:1a   C                     enx606d3c64581d
192.168.1.101                    (incomplete)                              enx606d3c64581d
192.168.1.247            ether   0c:8b:7d:f1:51:d3   C                     enx606d3c64581d
192.168.1.245            ether   ca:29:14:2b:92:39   C                     enx606d3c64581d
192.168.122.72                   (incomplete)                              virbr0
192.168.1.184            ether   8c:19:b5:b6:d3:c1   C                     enx606d3c64581d
```

#### What you just did

The arp (Address Resolution Protocol) command displays and manages the ARP cache, which is used to map IP addresses to MAC addresses.
Running arp -a on Windows or arp -n on Linux/macOS will show the current entries in the ARP cache, including IP addresses and associated MAC addresses.
The ARP protocol operates at the Data Link layer (Layer 2) and is responsible for resolving IP addresses to MAC addresses within the local network.

Well, we say "operates at Layer 2", but in fact, as you can see from the listing above, it's the go-between for Layer 2 (MAC addresses) and Layer 3 (TCP/IP addresses).  More on this later, maybe.

#### Screwdriver and pliers together

Let's try using the output of `ifconfig` and feeding it to another tool (`ethtool`) to get details.  Enter this command:

```nohighlight
ifconfig | grep -m 1 "^[a-z0-9]*:" | sed -e's/\(^[a-z0-9]*\):.*$/\1/' | xargs -I {} sh -c "ethtool {}"
```

The output might look something like this, depending upon which of your links is found first by `ifconfig`:

```nohighlight
Settings for enx606d3c64581d:
	Supported ports: [ TP	 MII ]
	Supported link modes:   10baseT/Half 10baseT/Full
	                        100baseT/Half 100baseT/Full
	                        1000baseT/Half 1000baseT/Full
	Supported pause frame use: No
	Supports auto-negotiation: Yes
	Supported FEC modes: Not reported
	Advertised link modes:  10baseT/Half 10baseT/Full
	                        100baseT/Half 100baseT/Full
	                        1000baseT/Full
	Advertised pause frame use: No
	Advertised auto-negotiation: Yes
	Advertised FEC modes: Not reported
	Link partner advertised link modes:  10baseT/Half 10baseT/Full
	                                     100baseT/Half 100baseT/Full
	                                     1000baseT/Full
	Link partner advertised pause frame use: Symmetric Receive-only
	Link partner advertised auto-negotiation: Yes
	Link partner advertised FEC modes: Not reported
	Speed: 1000Mb/s
	Duplex: Full
	Auto-negotiation: on
	Port: MII
	PHYAD: 32
	Transceiver: internal
netlink error: Operation not permitted
        Current message level: 0x00007fff (32767)
                               drv probe link timer ifdown ifup rx_err tx_err tx_queued intr tx_done rx_status pktdata hw wol
	Link detected: yes
```

#### What you just did

Apart from a little Rube Goldberg CLI magic, this command runs `ethtool` on a specific link to gather its details.  The `ethtool` command provides information and configuration options for Ethernet interfaces.  Running `ethtool <interface_name>` will -- as you see -- display details such as link status, speed, duplex mode, and supported features of the interface.  This command allows you to retrieve information about the Ethernet interface's capabilities and link status at the Data Link layer (Layer 2).

#### Layer 2 x-ray machine

Try the following command:

```nohighlight
ifconfig | grep -m 1 "^[a-z0-9]*:" | sed -e's/\(^[a-z0-9]*\):.*$/\1/' | xargs -I {} sh -c "sudo tcpdump -i {}"
```

You'll get a never-ending stream of network information (you can stop it by typing `Ctrl-c`; here's a typical digest of the first few lines:

```nohighlight
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on enx606d3c64581d, link-type EN10MB (Ethernet), snapshot length 262144 bytes
17:54:37.754586 IP ys-in-f102.1e100.net.https > neuromancer.home.32874: UDP, length 261
17:54:37.755120 IP neuromancer.home.32874 > ys-in-f102.1e100.net.https: UDP, length 35
17:54:37.755358 IP ys-in-f102.1e100.net.https > neuromancer.home.32874: UDP, length 1250
17:54:37.755358 IP ys-in-f102.1e100.net.https > neuromancer.home.32874: UDP, length 181
17:54:37.770914 IP neuromancer.home.52240 > router.home.domain: 20554+ [1au] PTR? 100.1.168.192.in-addr.arpa. (55)
17:54:37.772523 IP router.home.domain > neuromancer.home.52240: 20554* 1/0/1 PTR neuromancer.home. (85)
17:54:37.773830 IP neuromancer.home.59034 > router.home.domain: 38747+ [1au] PTR? 102.124.253.172.in-addr.arpa. (57)
17:54:37.790499 IP neuromancer.home.32874 > ys-in-f102.1e100.net.https: UDP, length 32
17:54:37.792160 IP router.home.domain > neuromancer.home.59034: 38747 1/0/1 PTR ys-in-f102.1e100.net. (91)
17:54:37.799052 IP ys-in-f102.1e100.net.https > neuromancer.home.32874: UDP, length 24
17:54:37.805083 IP ys-in-f102.1e100.net.https > neuromancer.home.32874: UDP, length 1218
17:54:37.805454 IP neuromancer.home.32874 > ys-in-f102.1e100.net.https: UDP, length 33
17:54:37.866323 IP neuromancer.home.46036 > router.home.domain: 55474+ [1au] PTR? 1.1.168.192.in-addr.arpa. (53)
17:54:37.868183 IP router.home.domain > neuromancer.home.46036: 55474* 1/0/1 PTR router.home. (78)
17:54:38.004210 d0:76:8f:e6:94:1a (oui Unknown) > 01:80:c2:00:00:13 (oui Unknown), ethertype IEEE1905.1 (0x893a), length 64: 
	0x0000:  0000 0000 6128 0080 0100 06d0 768f e694  ....a(......v...
	0x0010:  1a02 0006 d076 8fe6 941c 0000 0000 0000  .....v..........
	0x0020:  0000 0000 0000 0000 0000 0000 0000 0000  ................
	0x0030:  0000                                     ..
17:54:38.531517 IP6 neuromancer.dhcpv6-client > ff02::1:2.dhcpv6-server: dhcp6 solicit
17:54:38.533668 IP6 fe80::d276:8fff:fee6:941a.dhcpv6-server > neuromancer.dhcpv6-client: dhcp6 reply
17:54:38.594705 IP neuromancer.home.40063 > router.home.domain: 20998+ [1au] PTR? 2.0.0.0.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.0.f.f.ip6.arpa. (101)
17:54:38.614325 IP router.home.domain > neuromancer.home.40063: 20998 NXDomain 0/1/1 (165)
17:54:38.614802 IP neuromancer.home.40063 > router.home.domain: 20998+ PTR? 2.0.0.0.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.2.0.f.f.ip6.arpa. (90)
17:54:38.616383 IP router.home.domain > neuromancer.home.40063: 20998 NXDomain 0/0/0 (90)
17:54:38.895465 IP neuromancer.home.34598 > 192.168.1.247.8009: Flags [P.], seq 1620890202:1620890312, ack 1698989308, win 524, options [nop,nop,TS val 1031552033 ecr 2257976407], length 110
17:54:38.899322 IP 192.168.1.247.8009 > neuromancer.home.34598: Flags [P.], seq 1:111, ack 110, win 677, options [nop,nop,TS val 2257981415 ecr 1031552033], length 110
17:54:38.899435 IP neuromancer.home.34598 > 192.168.1.247.8009: Flags [.], ack 111, win 524, options [nop,nop,TS val 1031552037 ecr 2257981415], length 0
17:54:38.906072 IP neuromancer.home.33717 > router.home.domain: 50660+ [1au] PTR? 247.1.168.192.in-addr.arpa. (55)
17:54:38.907992 IP router.home.domain > neuromancer.home.33717: 50660 NXDomain* 0/0/1 (55)
17:54:38.908297 IP neuromancer.home.33717 > router.home.domain: 50660+ PTR? 247.1.168.192.in-addr.arpa. (44)
17:54:38.909967 IP router.home.domain > neuromancer.home.33717: 50660 NXDomain* 0/0/0 (44)
17:54:39.216802 STP 802.1d, Config, Flags [none], bridge-id 0000.d0:76:8f:e6:94:1a.8003, length 35
17:54:39.810480 IP neuromancer.home.42579 > yi-in-f100.1e100.net.https: UDP, length 176
17:54:39.828278 IP yi-in-f100.1e100.net.https > neuromancer.home.42579: UDP, length 28
17:54:39.839019 IP neuromancer.home.42579 > yi-in-f100.1e100.net.https: UDP, length 33
17:54:39.846436 IP neuromancer.home.44791 > router.home.domain: 8318+ [1au] PTR? 100.138.125.74.in-addr.arpa. (56)
17:54:39.865344 IP router.home.domain > neuromancer.home.44791: 8318 1/0/1 PTR yi-in-f100.1e100.net. (90)
17:54:39.871586 IP yi-in-f100.1e100.net.https > neuromancer.home.42579: UDP, length 619
17:54:39.871586 IP yi-in-f100.1e100.net.https > neuromancer.home.42579: UDP, length 35
17:54:39.871586 IP yi-in-f100.1e100.net.https > neuromancer.home.42579: UDP, length 252
17:54:39.872203 IP neuromancer.home.42579 > yi-in-f100.1e100.net.https: UDP, length 36
17:54:39.876566 IP neuromancer.home.42579 > yi-in-f100.1e100.net.https: UDP, length 33
```

#### What you just did

The tcpdump command is a packet analyser available on various Unix-like systems. By using specific filters, such as capturing packets on a specific interface (`-i <interface_name>`) or based on specific protocols, you can examine Layer 2 frames and their contents in real-time.  `tcpdump` allows you to capture and analyse network traffic, including Ethernet frames, providing insights into the communication at the Data Link layer (Layer 2).

These command line commands provide visibility into Layer 2 aspects of networking, such as MAC addresses, ARP cache, Ethernet interface configuration, and packet analysis. They can help you understand and troubleshoot issues related to Layer 2 connectivity, addressing, and protocols.  We'll come back to some of these tools much later on.

### Investigate IP addresses and routing

Type the following command and press Enter:

```nohighlight
ip address show
```

#### What you just did

This command will show the IP addresses assigned to your network interfaces. IP addresses operate at the Network layer (Layer 3) of the OSI model. You can see the assigned IP addresses, subnet masks, and other related information.

IP addresses are fundamental to network communication and are used at the Network layer (Layer 3) of the OSI model. An IP address is a unique numerical identifier assigned to each device connected to a network. It allows devices to send and receive data across networks, enabling communication between different devices and networks on the internet.

IP addresses consist of a series of numbers separated by periods (IPv4) or a combination of numbers and letters (IPv6). IPv4 addresses are widely used and typically written as four sets of numbers ranging from 0 to 255, such as "192.168.0.1". IPv6 addresses are becoming more prevalent and have a different format, represented as eight groups of four hexadecimal digits, separated by colons.

Now, type the following command and press Enter:

```nohighlight
ip route show
``` 

#### What you just did:

This command will display the routing table, which lists the available routes to different networks. It includes information about the destination network, gateway, and interface used for routing. Routing operates at the Network layer (Layer 3) of the OSI model.

Routing is the process of directing data packets from a source device to a destination device across interconnected networks. It occurs at the Network layer (Layer 3) of the OSI model. Routers, which operate at this layer, play a crucial role in the routing process.

When a device sends data to a destination, the data is divided into packets, each containing the source and destination IP addresses. Routers examine the destination IP address of each packet and determine the best path or route to reach the destination network. They make routing decisions based on routing tables, which contain information about available routes and associated metrics.

Routers use protocols such as OSPF (Open Shortest Path First) or BGP (Border Gateway Protocol) to exchange routing information and update their routing tables dynamically. This enables routers to adapt to changes in network topology, find the most efficient routes, and ensure that data packets are delivered accurately and efficiently across the network. Routing allows devices on different networks to communicate with each other, enabling data to traverse multiple networks and reach its intended destination.

### The Transport layer (Layer 4)

Type the following command and press `Enter`:

```nohighlight
ss -tunap
```

You'll see output that looks similar to this:

```nohighlight
tcp   LISTEN     0      128                                           [::]:17500                       [::]:*        users:(("dropbox",pid=2746,fd=59))         
tcp   LISTEN     0      10     [fe80::b9e0:1f84:f462:319a]%enx606d3c64581d:53                          [::]:*                                                   
tcp   LISTEN     0      10     [fe80::b9e0:1f84:f462:319a]%enx606d3c64581d:53                          [::]:*                                                   
tcp   LISTEN     0      10     [fe80::b9e0:1f84:f462:319a]%enx606d3c64581d:53                          [::]:*                                                   
tcp   LISTEN     0      10     [fe80::b9e0:1f84:f462:319a]%enx606d3c64581d:53                          [::]:*                                                   
tcp   LISTEN     0      10     [fe80::b9e0:1f84:f462:319a]%enx606d3c64581d:53                          [::]:*                                                   
tcp   LISTEN     0      10     [fe80::b9e0:1f84:f462:319a]%enx606d3c64581d:53                          [::]:*                                                   
tcp   LISTEN     0      10     [fe80::b9e0:1f84:f462:319a]%enx606d3c64581d:53                          [::]:*                                                   
tcp   LISTEN     0      10     [fe80::b9e0:1f84:f462:319a]%enx606d3c64581d:53                          [::]:*                                                   
tcp   ESTAB      0      0                         [fd42:60eb:6f56:329a::1]:5251    [fd42:60eb:6f56:329a::1]:44536                         
```

#### What you just did

This command will show active TCP and UDP connections on your system, along with their respective protocol information. TCP and UDP operate at the Transport layer (Layer 4) of the OSI model. You can see the local and remote IP addresses, port numbers, and connection states.


There's an old joke you can use to remember these options to `ss`: "You can tune a piano, but you can't tuna fish" (`ss -tunap`).


### Higher layer protocols

Layer 5 of the OSI model, the Session layer, primarily handles session establishment, maintenance, and termination between communicating systems. It is responsible for managing dialogue coordination and synchronisation. However, the Session layer is more abstract and typically implemented within the application layer protocols rather than being directly accessed through command-line commands. Layer 6 of the OSI model, the Presentation layer, is responsible for the representation and transformation of data in a manner that is independent of the application layer syntax. It focuses on ensuring that data from the application layer of one system can be properly interpreted by the application layer of another system.  Sadly, there are no specific command-line commands that provide direct, basic tutorial insight into Layer 5 and 6 functionalities. 

But we can certainly take a good look at Layer 7.  Type the following command and press `Enter`:

```nohighlight
sudo lsof -i
```

Representative output would look something like this, roughly:

```nohighlight
COMMAND      PID            USER   FD   TYPE  DEVICE SIZE/OFF NODE NAME
systemd        1            root  106u  IPv6   34911      0t0  TCP *:ssh (LISTEN)
systemd-r    948 systemd-resolve   13u  IPv4   31933      0t0  UDP localhost:domain 
avahi-dae   1116           avahi   12u  IPv4   28216      0t0  UDP *:mdns 
NetworkMa   1191            root   27u  IPv4   33515      0t0  UDP neuromancer.home:bootpc->router.home:bootps 
postgres    1379        postgres    3u  IPv4   35163      0t0  TCP localhost:postgresql (LISTEN)
dnsmasq     1744 libvirt-dnsmasq    3u  IPv4   38180      0t0  UDP *:bootps 
tor         1836      debian-tor    6u  IPv4   33600      0t0  TCP localhost:9050 (LISTEN)
slapd       1866        openldap    9u  IPv6   33551      0t0  TCP *:ldap (LISTEN)
proton-br   2680      stormrider   14u  IPv4   41368      0t0  TCP localhost:1143 (LISTEN)
dropbox     2746      stormrider   40u  IPv4 8770210      0t0  TCP neuromancer.home:46568->162.125.21.2:https (ESTABLISHED)
lxd         3550            root   20u  IPv6   41323      0t0  TCP *:8443 (LISTEN)
sshd      221835            root    3u  IPv6   34911      0t0  TCP *:ssh (LISTEN)
cupsd     328391            root    7u  IPv6 6125279      0t0  TCP ip6-localhost:ipp (LISTEN)
cupsd     328391            root    8u  IPv4 6125280      0t0  TCP localhost:ipp (LISTEN)
postgres  372592        postgres    5u  IPv4 7066887      0t0  TCP localhost:5434 (
chrome    405575      stormrider  310u  IPv4 8285829      0t0  UDP 224.0.0.251:mdns 
ssh       407687      stormrider    3u  IPv4 7680407      0t0  TCP neuromancer.home:57418->stormrider:ssh (ESTABLISHED)
python3   417174            root    9u  IPv6 7864004      0t0  TCP *:5249 (LISTEN)
rsyslogd  417289            root    5u  IPv4 7869618      0t0  TCP *:5247 (LISTEN)
chronyd   417291            root    3u  IPv4 7866040      0t0  UDP localhost:323 
named     417334            root   40u  IPv4 7867212      0t0  TCP localhost:954 (LISTEN)
squid     417573     snap_daemon    8u  IPv6 7868077      0t0  UDP *:48082 
nginx     417623            root    5u  IPv6 7873193      0t0  TCP *:5248 (LISTEN)
dhcpd     417667            root    9u  IPv4 7873979      0t0  UDP *:bootps 
```

As you can see, `lsof` lists open network connections and the associated processes on your system. It can help identify higher layer protocols and services running on specific ports. Protocols such as HTTP, FTP, SSH, or DNS operate at the Application layer (Layer 7) of the OSI model.  Understand that is isn't a process list, just a list of processes that are actively using network connections.