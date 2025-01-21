> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/a-primer-on-tcp-ip" target = "_blank">Let us know.</a>*

To design, operate, and troubleshoot MAAS networks effectively, you need a solid grasp of networking fundamentals.  Here, we've distilled the essentials for quick reference.

## The original Internet

If you ask a networking expert to briefly explain cloud architecture, you might get something like this:

> The traditional Internet infrastructure is an [access-aggregation-core (AAC)](https://www.cisco.com/c/en/us/td/docs/solutions/Enterprise/Data_Center/DC_Infra2_5/DCInfra_2.html)**^** network.  Mainframes were once epicentres. Monolithic applications ran with direct I/O connections, with routers as the multiplexing elements.  Lateral paths exist for performance reasons, like latency, redundancy, and cost.
>
> Because the focus was on hardware, switch-to-server ratios were high. These networks used hardware-based packet switching, rife with congestion issues and redundant loops known as "packet traps."  Eventually, the early Internet became a bottleneck because of unforeseen server-to-server traffic, leading to:
>
> - Shortage of Virtual LANs (VLANs)
> - Spanning Tree Protocol (STP) switch-count constraints
> - Packet flood complications
> - Risks of VLAN partitioning
> - ARP table overloads
>
> TCP/IP has a dedicated solution for this problem, called ["Time To Live"](https://en.wikipedia.org/wiki/Time_to_live#firstHeading)**^**.  Sadly, TTL reaches a point of diminishing returns with very large networks.  Over time, Local Area Networks (LANs) (like Banyan Vines) began to address this problem by joining CPUs from different machines. Today, generic switches and servers in a "spine-leaf" configuration make up both cloud and bare-metal clusters, shifting toward virtualisation."

If that seemed dense, don't worry: You're certainly not the only one who feels that way.  Let's explain that again, more slowly. In fact, let's start with the original network -- the telephone system -- and build slowly, following the evolution of modern cloud networks.  As we go, we'll offer some links to more detailed information, but don't feel obligated to follow those rabbit holes until you're ready.

## Yesterday's phone network is today's Internet

Modern networking is really just a direct translation of the landline telephone system into the digital space.  [Network switching](https://en.wikipedia.org/wiki/Network_switch#firstHeading)**^** is an outgrowth of [crossbar](https://en.wikipedia.org/wiki/Number_Five_Crossbar_Switching_System#firstHeading)**^**, which is how local phone calls were "switched" or "routed" to the correct phone line.  Every number dialled closed one more relay, with all seven relays making a complete circuit between telephones.

For a telephone technician, monitoring local traffic on a connected printer, it might have looked something like this:

```nohighlight
Off-hook condition: 555-1287
Digit dialed: 5
Circuit routed to open frameset, relay 5
Digit dialed: 5
Circuit diverted to open frameset, relay 5/5
Digit dialed: 5
Circuit diverted to local exchange frameset
Digit dialed: 3
Circuit diverted to LE subrelay 3
Digit dialed 2
Circuit diverted to LE sub 3/2
Digit dialed 7
Circuit diverted to LE sub 3/2/7
Digit dialed 4
Circuit diverted to LE sub 3/2/7/4
Circuit complete
Initiating ring signal
One ring on 555-3274
Off-hook on 555-3274
Call connected; timer started
```

These [framesets](https://en.wikipedia.org/wiki/Distribution_frame#firstHeading)**^** were the automated equivalent of having a switchboard operator find the right plug and connect the plug for your line (1287) to the plug for the called party (3274).  Over time, these relay networks got much simpler by allowing exchanges to "swallow" dialled digits. 

For example, if every local phone number had the exchange "881", a local call wouldn't trigger any relays beyond just sending the call to the "881" frameset.  In some small exchanges, it wasn't even necessary to dial the exchange, just the four digits of the phone number, if the caller had the same exchange.  Networks still swallow digits today, they're just called [subnets](https://en.wikipedia.org/wiki/Subnetwork#firstHeading)**^**.

## Complexity with growth

Over time, the increasing density of telephone coverage (and self-service long-distance) changed all this.  More wires had to be installed.  Local exchanges were replaced by centralised exchanges called "central offices" (CO).  A CO would have frames for 8 or 10 exchanges, essentially serving the same function as today's network [routers](https://en.wikipedia.org/wiki/Router_(computing)).

Repeaters (voltage boosters) were needed to get signals across longer distances. These "go-away-grey" metal cans (called pedestals) popped up everywhere, partly for wire re-routing, and partly to house repeaters.  We still have those in today's cloud networks, but they're called [patch-panels](https://en.wikipedia.org/wiki/Patch_panel).

In the very early days of long-haul networking, most of the repeaters were owned by the local telephone companies. T1 lines, or [T-carriers](https://en.wikipedia.org/wiki/T-carrier), as they were officially called, provided a speedy (at the time) 1.5Mbps phone connection.  They carried several phone calls on one line via [Time-Division Multiplexing](https://en.wikipedia.org/wiki/Time-division_multiplexing).  TDM split up the call traffic into little digital packets that were sent on a rotating basis.  We still do TDM today, we just call it [TCP](https://en.wikipedia.org/wiki/Transmission_Control_Protocol).

The first T1 lines, which showed up around 1962, could handle about 24 calls without the average telephone user noticing.  Telephone linemen generally could tell by the "clipped" nature of the call, as there is a distinctive flatness to the conversation over a digital TDM circuit.  Raw audio is too large to be efficiently transmitted, so it was sampled in "little digital packets" which were mixed in with other packets from other calls.  T1 could rotate through 24 calls, sending the next packet of audio before the listener's ear could fully process the first packet.  We have that today: it's called [packet-switching](https://en.wikipedia.org/wiki/Packet_switching).

The T1 lines used ordinary, double-twisted-pair copper wiring, with repeaters at roughly one-mile intervals (about every fourth pedestal in the modern phone system). When WAN and MAN networking became a thing, the phone company just repurposed some of those pairs to carry data traffic.  Many other key elements of TCP/IP, like twisted-pair Ethernet cables, packet-based messaging, and multiplexing, are all just holdovers of the original telephone system, repurposed for computer networking.

### Internet infrastructure gets complicated

The Internet is theoretically survivable because every computer can connect to every other computer.  That's not standard operating procedure.  High-level networks [(Network Service Providers, NSPs)](https://en.wikipedia.org/wiki/Internet_service_provider#firstHeading)**^** connect to at least three top level nodes called Network Access Points (NAPs), aka [Internet Exchange Points](https://en.wikipedia.org/wiki/Internet_exchange_point#firstHeading)**^**.  At these points, packets to jump from one NSP to another. NAPs are public access points, Metropolitan Area Exchanges are private. These are virtually indistinguishable for the purposes of this discussion.
 
As an aside, many of the MAEs are the residue of the phone company's early T1 lines, which was the initial backbone for the Internet.  These MAEs act just like a NAP for the purposes of this discussion.  Put this all together, and it looks like a big ladder.  There are lateral (sideways) connections at every level for both performance and cost reasons: performance, because the path from a computer on one NAP to another is too slow; cost, because each of those top-to-bottom layers is somebody else's network, which means, basically, usage fees.  Shortcut connections are faster and cheaper.

### Internet traffic

The real Internet has lots of these shortcut connections. Each one has an interface cost (heterogeneous hardware), a performance cost (varying network speeds), a bandwidth cost (differing traffic levels), and a dollar cost (somebody else's wires).  This is why contracts for connections change daily, which changes the routing, which changes the way the Internet behaves for users.

Internet paths are complicated and unpredictable.  There not much value in counting how many hops a message takes, or where it hops, unless you're trying to debug a broken route with, say, [traceroute](https://linux.die.net/man/8/traceroute)**^**.  From a TCP/IP point of view, it's much easier to ignore the specific network, since each one is custom built on-the-fly.  The path can theoretically change every time a message is sent, even between the same two computers.

When it comes to designing and troubleshooting networks, knowing the specific route (almost) never helps.  What we do want to know about is the network traffic between computers.  We have to understand what kind of data travels between computers, besides just the data we send.  To help us take the wires out of the equation, Internet data flows are governed by the [OSI model](https://en.wikipedia.org/wiki/OSI_model).

## The OSI model

Networks are really just switched circuits.  What really matters is the traffic flowing on those circuits, which depends on our perspective -- our level of magnification.  At the highest "zoom" level, all we'll see are electrons travelling down the wire; that's a level of abstraction that isn't comprehensible for debugging purposes.  About all we can tell is whether or not the circuit's dead.

The OSI model starts just above the raw physics, with the physical layer, also known as Layer 1.  Starting with "1" makes sense, because this is the lowest level we consider. Layers are normally added on top of each other.  For example, if you put six coats of varnish on a piece of furniture, you're going to have six layers.  The first layer you put on wouldn't sensibly be called "layer 6"; neither network layering work that way.

Here's a quick rundown of what each layer does.  Most likely, we won't get into details about all the layers, because the higher you go, the more widely they vary with the user application -- and higher layers don't really help us better understand MAAS networking, any more than watching electrons travel through a wire will help us debug a missing packet.

### The physical layer (L1)

The phrase "physical layer" may conjure up notions of physics, but don't worry: we look at signals, not electrons.  Here you can learn about the basics of the physical layer.

At the physical layer, we're looking for binary (on/off) signals, set to the cadence of a clock.  Every computer brings its own clock to the party, so we definitely need a way to "synchronise our watches".  [NTP](https://en.wikipedia.org/wiki/Network_Time_Protocol)**^**, the network time protocol, does the trick.  

#### Variable latency

Variable latency is the important thing to know about the physical layer, because it affects the timing of network traffic. In order to understand variable latency, we need to understand network latency.  Packets aren't sent without some delay, because of:

1. The processing delay - how long it takes the router to process the packet header.
2. A queuing delay - how long the packet sits idle in routing queues.
3. Transmission delay - how long it takes layer 1 to push the packet's bits onto the link.
4. Propagation delay - how long it takes the bits to travel through the wire to the other end.

The size of the queue directly influences how fast data can get onto the link.  The processing and transmission delays are real, though relatively constant.  The propagation delay doesn't just depend on the speed of light, because there may be lots of other "relay" computers in the link.  Propagation depends on network architecture, network congestion, and the number of hops (how many routers between source and destination), among other things.  As we'll see later on, within your enterprise, [modern cloud architectures](#About-cloud-networks) usually create significantly less propagation delay.

Variable-latency networks are "variable" because of the density of network traffic and the complexity of the route between hosts.  We can't predict congestion or routing, although we can influence local routing by choosing the right network architecture.  We can't predict transmission delays, though we can statistically bound them.  Almost all digital networks are considered "variable-latency".

#### The physical layer is not very interesting

Other than verifying that signals are flowing, the physical layer doesn't usually tell us much about what happened to that DHCP request that never made it to the router.  Consequently, we really won't talk that much about the physical layer.  Just know that it's the thing that's passing bits back and forth between hosts, and very occasionally, we need to scan it to debug network issues.

### The datalink layer (L2)

The datalink layer (the "link" layer, layer 2 or "L2") has one purpose: send and receive IP datagrams.  L2 doesn't maintain a connection with the target host; it's intentionally "connectionless", and it doesn't guarantee delivery or integrity of packets.  It just ships them between source and destination.  At first, in fact, the message-agnostic state of the link layer may seem a little weird.  L2 is not without error-checking and recovery code, but it functions efficiently because it isn't concerned with the data or the message containing the data.  That fact can be surprising, since L3 packets are called "datagrams".

A datagram is just a basic network transfer unit -- the indivisible unit for a given layer.  If we're talking about the data-link layer (aka the "link" layer), it's an IEEE 802.xx frame.  At the network layer, it's a data packet.  For the transport layer, it would be called a segment.  Indivisible units in the physical layer are called chips, which are spread-spectrum pulses in the CDMA, noise-utilising transmission system that operates at that layer.

Since datagram isn't carefully used by everyone (think of User Datagram Protocol), we'll agree to call these indivisible layer units PDUs (protocol data units).  This avoids conflation with other uses and reminds you that it's the atomic unit at the current network layer.  Just remember that, at the link layer (L2), it's a frame.

#### MAC frames

A MAC frame, or just "frame", encapsulates the packets from the network layer so that they can be transmitted on the physical layer.  A frame can be small or big, anywhere from 5 bytes up to the kilobyte range.  The upper size limit is called the maximum transmission unit (MTU) or maximum frame size.  This size is set by the particular network technology in use.

This last observation brings up a good point: In order to talk sensibly about frames, we'd need to say what kind of frame.  With MAAS, we're always talking about packet-switched networks, so there are potentially four frame types to consider: Ethernet, fibre channel, V.42, and PPP (point-to-point protocol).

Happily, MAAS networks almost exclusively use Ethernet, as defined in the [IEEE 802 standards](https://www.ieee802.org/)**^**, so we'll stick to that particular frame type for this discussion.  Where other frame types may come into play, we'll discuss those as special cases.  

#### Ethernet

Before explaining an Ethernet Frame, we need to give a little background information about how Ethernet works; otherwise a lot of the frame components either won't make sense, or you'll wonder how it works at all.

Remember earlier, when we talked about voice radio, and the need to say "over"?  Well, Ethernet at the link layer is all about controlling the conversation, so that computers don't "talk over each other".  Ethernet implements an algorithm called CSMA/CD, which stands for "carrier sense multiple access with collision detection."  This algorithm controls which computers can access the shared medium (an Ethernet cable) without any special synchronisation requirements.

"Carrier sense" means that every NIC does what humans do when we're talking: it waits for quiet.  In this case, it's waiting for the network to be quiet, that is, when no signal is being sent on the network.

"Collision detection" means that, should two NICs both start to send on a shared network at the same time (because the network was quiet), they each receive a jam signal.  This signal tells them to wait a specific, randomly-generated amount of time before attempting again.  Every time subsequent messages collide, the NIC waits twice the amount of time it previously waited.  When it waits some maximum number of times, the NIC will declare a failure and report that the message didn't go.  This ensures that only one frame is traversing the network at any given time.

#### Media Access Control (MAC)

Systems like CSMA/CD are a subset of the Media Access Control (MAC) protocol kit.  MAC is one-half of the link layer, with Logical Link Control (LLC) being the other half -- though these are sometimes called sub-layers. LLC mostly just defines the frame format for the 802.xx protocols, like WiFi, so we can safely ignore it for the purposes of MAAS networking.

If you've worked with networks at all, you've heard of MAC addresses.  Those are basically unique serial numbers assigned to network interface devices (like NICs) at the time of manufacture.  Theoretically, they are unique in the world, not counting virtual NICs in virtual machine environments.  [MAC address collisions](https://kb.vmware.com/s/article/219)**^** do happen when using VMs, and there are ways to fix it, assuming that your VMs are confined to a subnet.

The MAC sub-layer is connected to the physical layer by a media-independent interface (MII), independent of the actual link protocol (e.g, cellular broadband, Wi-Fi radio, Bluetooth, Cat5e, T1, ...).  You can learn more about the [MII](https://en.wikipedia.org/wiki/Media-independent_interface)**^** if you're so inclined, but we won't address it again in the context of MAAS networks.

Essentially, the MAC sub-layer grabs higher-level frames and makes them digestible by the physical layer, by encoding them into an MII format.  It adds some synchronisation info and pads the message (if needed).   The MAC sub-layer also adds a frame check sequence that makes it easier to identify errors.

In conventional Ethernet networks, all this looks something like the following:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/1/14f6847ed92339061eb4515c12ac2b6117d5cd7c.jpeg)

Let's decode those blocks of bits:

- The **Preamble** is 7 bytes of clock sync, basically just zeroes and ones like this: ...0101010101....  This gives the receiving station a chance to catch up and sync their clock, so the following data isn't out of sync (and thus misinterpreted).  To delve just a little deeper, the Preamble helps the receiving NIC figure out the exact amount of time between encoded bits (it's called clock recovery).  NTP is nice, but Ethernet is an asynchronous LAN protocol, meaning it doesn't expect perfectly synchronised clocks between any two NICs.  The Preamble is similar to the way an orchestra conductor might "count the players in" so they all get the same rhythm to start.  Before clock recovery, there was MPE. Clock recovery is much more reliable than trying to get computers all over the world synced up to the same clock frequency and the same downbeat (starting point).  Ethernet actually started out that way with something called Manchester Encoding or Manchester Phase Encoding (MPE).  This was important because electrical frequency varies not only across the world, but also from moment to moment when the power is slightly "dirty".  MPE involved bouncing a bit between two fractional voltages using a 20MHz oscillator to generate a reference square wave.  It works, but it's not very efficient, so MPE was scrapped in favour of using the Preamble, the way that projectionists use alignment marks on reels of movie film.
   
- The **Start Frame Delimiter (SFD)** is the last chance for clock sync.  It is exactly 10101011, where the "11" tells the receiving station that the real header content starts next.  The receiving NIC has to recover the clock by the time it hits the SFD, or abandon the frame to the bit bucket.

- The **Destination Address (DAddr)** is six bytes long, and gives the physical address -- the MAC address -- of the next hop.  Be aware that the next hop might be the destination, but it's also possible that the next hop might be a NAP, MAE, NSP, or intermediate ISP.  It's basically the next address in the direction of the destination that the sender knows about.  Unlike the Source Address, the Destination Address can be in a broadcast format (similar to a subnet like 192.18.0.0, but using MAC addresses).

- The **Source Address (SAddr)** is also a six-byte MAC address, this time the MAC address of the sender, which does not change as long as the message is traversing only layer-2 (Ethernet) switches and routers.

- The **PDU Length (PDULen)** gives the byte length of the entire frame, assuming that it's 1500 or less.  If it's longer than that, it indicates a message type, like IPv4, ARP, or a "q-tagged" frame, which carries a VLAN ID.

- The **DSAP**, **SSAP**, and **Control** elements are each one byte in length, and help define devices and protocols.  For the most part, we won't be worried about these with MAAS networks.  Just know that as more and more 802 point-standards come out (e.g., 802.11, WiFi), these elements get longer and more complex.

- The **Data** or "Payload" is the actual packet being sent, which in the case of TCP/IP, is just a TCP header attached to a fixed-length chunk of the application's data.  It's passed on from the layer above.  It cannot be less than 46 bytes, and in conventional Ethernet, it cannot be larger than 1500 bytes.  If the actual data is too small, it's padded out to 46 bytes.

- The **CRC** or "Frame Checksum" (FCS) is a standard checksum, used to verify that the message hasn't been corrupted along the way.

The Preamble and SFD are often considered to be part of the IEEE "packet", so some people start counting the "frame" at the Destination Address.  That distinction shouldn't affect anything we do with MAAS networks, but it's nice to keep in mind, in case you run into someone who groups packets differently than you do.

#### Trunking VLANs

There is a crucial modification to the basic frame format called a P/Q or VLAN Tag.  This allows something called VLAN trunking, which means sending all the VLAN data over the same wire and port, but giving the NICs a field (the P/Q tag) to control access.  On paper, it looks something like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/6/6e58930520fe4ed38d5ea49fab7a337627a88a55.jpeg)

As you can see in the modified P/Q frame, the following fields replace part of the frame:

- Sixteen bits of tags or a protocol ID.

- Three bits representing a priority.

- One bit is used as a Canonical Format Indicator (CFI), which is 0 if the following VLAN ID is in Ethernet format, or 1 if it's in Token Ring format.

- Twelve bits of VLAN ID.

This matters when we're building complex MAAS networks with lots of VLANS that probably cross over switches.  After all, VLANs were initially controlled with ports and switches, although they more commonly use tags now.  When more than one VLAN spans multiple switches, frames need to carry VLAN information that can be used by switches to sort or "trunk" the traffic.

#### The origin of "trunking"

The word "trunking" is derived from the telephone network term trunk lines, which are lines connecting switchboards.

In the original telephone company model, each telephone had a subscriber line, which was a wire that went straight from the local Central Office (CO) to that subscriber's telephone.  Each CO had one switchboard, though it might have many seats.

Connections between Central Offices were handled by trunk lines, because they ran between phone company facilities.  You'd have a thick cable with lots of pairs running from CO to CO, basically enough wires to handle something like 35% of the possible calls.  If you ever got the message, "All circuits are busy now; please try your call again later", you've heard what happens when the system is "trunking above capacity" or "TAC'd", as it was called.

At the CO, the wires would "branch" and run all over the place: First to junction points (those five-foot-tall boxes you see from time to time on the road), then to interface points (the square cans beside the road every half mile or so, also called "pedestals") and from there to subscriber homes.  When you draw out this network, it looks like a tree, where the bundles of cables between COs look like the trunks of trees.

With VLAN trunking, by the way, we're not just multiplexing packets, we're actually multiplexing LAN channels, so to speak.  

In the parlance of networks, especially VLANs, the term "trunking" is used to indicate the sharing of network routes.  This sharing is made possible by the Ethernet VLAN tags, which make the VLAN-bound messages less dependent on switches and routers to get the traffic to the right place.  Otherwise, you'd have to designate complicated port configurations for switches, which is particularly easy to misconfigure.

Note that the MAC sub-layer is responsible for managing CDMA/CD, that is, detecting a clear line, initiating re-transmission if there's a jam signal, etc.  On the way in, the MAC sub-layer verifies the CRC/FCS and removes frame elements before passing the data up to the higher layers.  Basically, anything that some other MAC layer did to encapsulate the message for sending, the receiving MAC layer un-does on the way in.

#### VLANs, subnets, and fabrics

When working with MAAS networks, you will frequently be concerned with VLANs, subnets, and fabrics, which are all network groupings:

- Subnets define (group) a range of IP addresses.
   
- VLANs group subnets.

- Fabrics group VLANs.

Let's give each of these terms a MAAS context.

**Subnets**

A subnet is a range or collection of IP addresses.  A subnet just means "sub-network," and that's exactly what it is: a subset of IP addresses that can be treated like a single block for some operations.

Subnets are defined in CIDR (Classless Inter-Domain Routing) notation. If you want to use the addresses from 192.168.13.0 to 192.168.13.255 in a subnet, you can specify that with 192.168.13.0/24.  The "24" refers to the number of bits in the subnet address, with the remainder out of 32 bits free to address hosts.  Since 8 bits can represent 256 things, that means /24 gives you the last octet, or 255 host IP addresses.

**Whatever happened to subnet classes?**  Subnets used to be defined in terms of subnet classes, like A, B, and C. That got to be a limitation, because those three classes define a fixed number of bits of the IP address that represent the split between subnet addresses and host addresses.  In other words, the class defined how many hosts could be in the network, and three classes wasn't really adequate to address all the possible permutations that network architects needed.  The change to CIDR notation made subnets more granular, allowing many more subnets from the same network.

**VLANs**

A VLAN used to be a series of IP addresses that could access a given port on a specific switch, generally the switch that gated some protected resource.  With the advent of VLAN trunking (see above), VLANs are marked with the 802.1Q (P/Q) bits in the MAC frame.  In theory, any set of addresses can be associated with any VLAN.

MAAS encourages a correspondence of subnets to VLANs. Every IP should be in exactly one subnet, and every subnet should be part of exactly one VLAN.  You don't have to do that: you could, for example, have two different subnets that overlap, like 192.168.43.0/24 and 192.168.43.0/26.  The ".26" subnet would use fewer bits for the host addresses, so only some of the addresses would overlap.  MAAS generally prevents this kind of address overlap.

Likewise, putting one subnet in two different VLANs might be possible, but it isn't practical or easy to debug when conflicts happen.  MAAS endeavours to enforce a clean "fan-out" across the network, with no possibility of conflicting IP addresses.

**Fabrics**

A fabric just collects VLANs together.  If you stick to the clean fan-out, that also means that a fabric collects subnets.  A fabric provides a higher level grouping.

Consider a MAAS-centric example.  Suppose you have one VLAN for HR, and one VLAN for payroll, so that nobody else can see HR's private files, and likewise you've got payroll data limited to just those people who should see it.

Some executives are entitled to see anything and everything about the corporation.  An "executive" fabric would group all VLANs together, so that people admitted to that fabric can access the VLANs without having to be explicitly added to each one.  That's very handy in really large organisations, saving a lot of time and effort.

#### Visualising the link layer

Let's start with a message coming on Layer 1 from SanDiego to Bangor. When the message comes in, the link layer does the following things:

1. It synchronises the NIC, so that bits will indeed be recognised as bits and the message can be properly decoded.

2. It handles the source and destination addresses, using ARP as necessary. 

3. It interprets the length/type bytes and uses them, which means it must judge the length of a frame, and of the data in a frame, or, alternatively, decide whether a frame is IPv4, ARP, or VLAN ("q-tagged").  

4. It processes VLAN tags, which means, at the very least, dealing with the message priority, deciding whether the VLAN frame is Ethernet or Token Ring, and capturing and using the VLAN ID.  The layer handles messages by priority, knows how and when to send Ethernet or Token Ring frames, and knows how to route traffic to a specific VLAN.

5. It computes the checksum to make sure the message is valid.

Next, we'll take a look at the network layer, where most of the message transactions take place, and where most of our debugging will be done.

### Interlayer addressing: ARP

One frequently asked question is this: Is ARP a layer 2 or layer 3 protocol?  Actually, it's both, as you'll [discover later](#heading--about-arp), but it does all of its work at L2.  One way to distinguish L2 from L3 is to find out what happens inside the firmware of the Network Interface Card (NIC), and that's usually where ARP takes place.   ARP maps MAC addresses, which is how things are addressed in L2, into other addresses (e.g., IP addresses), which is how L3 finds things.

### The network layer

You might have noticed in the original OSI model that "IP" was part of Layer 3, and protocol stacks like UDP and TCP were part of Layer 4.  It's a little bit confusing that we say "TCP/IP" when the "IP" really applies to so many other protocols like UDP and ICMP.  There are certainly other protocols and protocol stacks, but for the purposes of MAAS networks, we're talking almost exclusively about TCP/IP.

The network layer does not guarantee delivery.  Essentially, it makes every effort to deliver IP datagrams (packets) to the destination, but it's error-handling is pretty simple: just toss the packet into the bit-bucket.

It's also a connectionless layer, meaning the packets making up a message aren't part of an ongoing conversation.  They can be split up, encoded, and sent separately, by different routes, and arrive completely out of order.  And packets can get duplicated or corrupted.  Figuring all this out is the job of the protocol stack (e.g., TCP) in layer 4.  The network layer, L3, just delivers packets.  

**Network byte order**: A rarely needed (but useful) fact is that the network sends bytes in big endian order.  That means bytes are transmitted starting with bit 0 and working down to bit 31, usually eight bits at a time.  A lot of the computers on the Internet use little endian encoding, which starts at the other end of the word.  In those cases, the byte order has to be reversed somewhere between the computer's memory and Layer 3. For most situations, that fact isn't particularly useful, but there is the occasional fault that involves failure to reverse byte order along the path from RAM to NIC.

#### Packets

Packets are basic Internet Protocol (IP) message units.  A message will probably be split into multiple packets by L4 (the transport layer) so it can be efficiently sent.

For example, imagine that you're sending a very long letter to your friend, and all you have are lots of envelopes and first-class stamps.  If you've ever done a lot of mailing, you'll know that mailing a one-ounce letter costs you, say, fifty-eight cents.  If you add another ounce of paper to it, that second ounce only costs you, say, twenty cents.  But all you have are first class (i.e., fifty-eight-cent) stamps.

If you don't want to waste your money, you can either cram more pages in the envelope, until you're at three ounces (the most you can get with two stamps), or send two letters, each with one ounce in it.  The way envelopes go through the mailing system, you're better off not over-stuffing an envelope.  So what do you do?

You sit down and write the letter to your friend, carefully numbering the pages.  Then you divide it into piles of pages that are just under one ounce. Finally, you put each pile into an addressed, stamped envelope and mail each letter separately.  When your friend gets the letters, it doesn't matter which one gets there first, because they can reassemble your message, using the page numbers.

#### Fixed packet lengths and segmented messaging

We could have designed computer networks to take messages of indeterminate lengths, but that presents some unique challenges when trying to manage network traffic.  For example, suppose you send seven overstuffed letters to your friend, and so does everyone else on your block?  All these huge letters aren't going to fit in one letter-carrier's bag, so they'll have to either send out two delivery people, or wait until tomorrow to send out someone's letters.

Choosing a fixed (relatively short) length makes it statistically possible for everyone's letters (everyone's messages) to be delivered at a fairly constant, reliable rate.  That rate will vary with the size of the overall message, not with who threw their message on the Internet first.  A larger message takes longer to send.

Messages are split into packets of consistent length before they're passed to L3, so larger messages take longer.  It's statistically more efficient to split messages into equally-sized packets than any other arrangement -- the method that gets the highest count of complete messages through the network in a given amount of time. In network terminology, it's the highest-throughput approach to network traffic.  Specifically, this technique is called multiplexing.

#### IP packets

The IP datagram (packet) is the backbone of most modern networks.  The following diagram depicts an IPv4 header, which attaches to the front of data packets up to about 65K long:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/fc349972f6b7509b5b2459bf3bb44419961f0bcd.jpeg)

Note that IPv6 headers have only the version field in common with IPv4 headers; otherwise, they are completely different.  Here are the header fields and what information they carry:

- **IP Protocol Version**  This is "4" for IPv4 and "6" for IPv6.  There are [lots of others](https://www.iana.org/assignments/protocol-numbers/protocol-numbers.xhtml)**^**, but they generally don't touch a MAAS network.
- **Internet Header Length** The number of 32-bit words in the header, including the options (but not including the data, since it's just the header).  Most of the time, this will have the value "5", but options do exist and are sometimes included.
- **Differentiated Services Code Point** This is used to specify special classes of service.  Normally, IP packets are delivered on a "best-effort" basis, that is, Layer 3 will try everything possible to make sure a packet gets delivered.  You can cause L3 to deliver packets with higher priority (implying more certainty) by using a different DSCP.
- **ECN = Explicit Congestion Notification** These bits are both set by an ECN-capable router when that router is above a certain traffic threshold.  They are there to alert a sender to slow down (or expect delays) when the network segment in use is particularly congested.
- **Total Length of IP Packet** This field indicates the length of the entire packet, including the data.  This makes it possible to calculate the byte offset of the data within the datagram.
- **Identification**  This is a serial number, generated by the sending NIC, that helps the participants uniquely identify the datagram.  In a sense, it works like the little "take-a-number" tickets you get at the hamburger stand: Eventually, the number will repeat, but the repeat cycle is so long that there's no chance of confusing packets.  The sequential nature of this field, when used in concert with the Flags and Fragmentation Offset field, helps the protocol stack correctly reassemble the message.
- **Flags**  This field is basically used to indicate that a packet is a fragment of a longer message.
- **Fragmentation Offset**  Used with the Identification sequence number, this field allows the system to know which packets precede or follow this one when re-assembling the message.
- **Time to Live (TTL)**  This indicates the number of routers that a datagram can pass through before it's discarded.  Since routers function by replacing their own destination address with the IP address of the next hop, this essentially limits the number of times a packet's destination IP can be changed.  Most RFC documents suggest keeping this number at 64, it's more often set to something like 255 without any real bottlenecks.
- **Protocol** This field indicates the higher level protocol (the protocol stack) that generated this message.  Examples are given for TCP and UDP in the figure.
- **Header Checksum** This calculates a checksum for the header only.  It's only used in IPv4.  Doing integrity-checking on the data is the responsibility of Layer 4.
- **Source Address** This is the IP address of the sender of the packet, for this hop only.  As shown in the figure below, routers will change this address so they can get the answer back.
- **Destination Address**  This is the IP address of the destination, for this hop only.  As shown below, routers change this address to act as brokers in the IP chain.

#### Routing

We now have enough concepts in play to talk about routing.  Routing takes place at the network layer, by changing the source and destination addresses (without losing track of the replaced address).  The process looks something like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/7/73c49cb76573e42036c59832f5f16b6383fbc0bd.jpeg)

The router typically assigns a unique port number to the outbound message, and records the source IP against that port number.  When the message comes back to it on that port number, it can look up the IP address of the NIC that sent the packet and route the answer back.

### The transport layer

Layer 4 brings us to protocols implemented only by the end hosts (i.e., not by the routers or other switching gear that connect the network).  This layer handles things like redundancy, confirmed delivery, managing packets on an unreliable network, and so forth.  This is the last layer that TCP/IP has anything to say about; layers above this are unique to specific applications.  Troubleshooting this level would involve knowing about entire protocol sets, like UDP or TCP.

### The session layer

Layer 5, the session layer, is where ongoing interactions between applications happen. The data is couched in terms of things an application might understand (e.g., cookies for a Web browser).    This is also the layer where check-pointing (i.e., saving work finished so far) happens.  At this layer, we'd discuss things like RPC, SQL, or NetBIOS.

### The presentation layer

The presentation layer converts data between formats and ensures standard encodings are used to present the information to the application. This layer is all about file formats: ASCII, EBCDIC, JPEG, GIF, and HTML, to name just a few.

### The application layer

The top layer, layer 7, is totally the province of the application(s) involved in processing messages.  Two techs talking about this layer would be swapping stories about application protocols, like FTP, DNS, SMTP, or NFS.  Almost nothing that happens at this layer -- except for throughput estimates or fouled daemon code -- filters into designing or debugging MAAS networks.


## Bond interfaces

A bond interface is used to aggregate two or more physical interfaces into a single logical interface. Combining multiple network connections in parallel can increase network throughput beyond what a single NIC will allow.  It also provides some redundancy in case one of the NICs should fail.

Bonded interfaces use a special frame format called LACPDU, or "Link Aggregation Control Protocol Data Unit.  More information about these special frames, and about the theory behind bonded NICs, can be found in the [relevant IEEE standard](https://1.ieee802.org/tsn/802-1ax-rev/)**^**.

## Bridge interfaces

Let's take a short diversion to talk about bridge interfaces.  These will be important when we discuss ARP a little further down.

A network bridge may be useful if you intend to use virtual machines or containers with MAAS.  Bridges are, to some extent, artefacts of the AAC network.  Frequently, people ask about the difference between a switch and a bridge.  The core answer lies in the number of ports: switches have as many ports as you can afford; bridges usually have fewer ports, often only two.

Switches traditionally forward packets, without storing them, to a specific host on a specific port, building up a table of host vs. port in the process to reduce broadcast transmissions. Switches traditionally use ASICs (Application Specific Integrated Circuits), otherwise known as "merchant silicon", designed especially for that purpose.

Bridges, on the other hand, provide store and forward packets between two LANs, generally using software.  They might still integrate merchant silicon, or even start as an ODM (original design manufacturer) box with no NOS (network operating system), similar to the way some mid-range switches are built.  Software added on top, plus the low port count and the store-and-forward approach.

Bridges can use MAC addresses (L2) to direct packets, can essentially emulate L3 routing (recording IP addresses of bridged messages for correct return trips), or some combination of both.  Switches usually just route packets between ports.

You can create a network bridge with MAAS; via netplan; or by any other established method to create a network bridge.  For example, when you're using LXD, you typically create a virtual bridge, called `lxdbr0` by default, that bridges between the MAAS host and the LXD instance.  On the host side, the LXD bridge looks like this:

```nohighlight
7: lxdbr0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default qlen 1000
    link/ether 00:16:3e:e4:2b:fe brd ff:ff:ff:ff:ff:ff
    inet 10.90.194.1/24 scope global lxdbr0
       valid_lft forever preferred_lft forever
    inet6 fd42:1fc6:f588:d0b8::1/64 scope global 
       valid_lft forever preferred_lft forever
    inet6 fe80::216:3eff:fee4:2bfe/64 scope link 
       valid_lft forever preferred_lft forever
```

On the MAAS side, the virtual bridge looks like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/fbdef2010657939f5f25ee2f157ba5a92af72090.png)

Where the 10.190.94.0/24 network is usually part of a VLAN offering MAAS-provided DHCP:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/1/1067a379ba9411713ed1a67e78e249535771b08c.png)

There are other DHCP configurations possible with MAAS (we'll cover this later).  The important point here is not to get overly hung up on the terms "switch", "bridge", and "router".  Instead, figure out whether you want to forward messages based on port numbers, MAC addresses, or IP addresses -- or some combination -- and then find real or virtual devices that will do this for you.

## ARP
 
In theory, every NIC card in the world has a unique identifier, called a /MAC address/.  "MAC" stands for "Media Access Control" -- you can find a [little history of this](https://en.wikipedia.org/wiki/Medium_access_control)**^** on Wikipedia, if you're interested.

When you're assigning MAC addresses with virtual machines, of course, you may be re-using one that's actually assigned to a network device out there somewhere.  Inside your Layer 2 network, that isn't a problem, because only devices connected to a physical switch -- that's actually connected to the physical Internet -- care about unique MAC addresses.  Inside your network, the only conflicts you need to worry about are the ones you create by hand-assigning MAC addresses.

The shorter answer to that implied question is this: MAC addresses must be unique across the domain where they're used.  

### TCP/IP does not use MAC addresses

If we look at the IP datagram again, we see that it doesn't know about MAC addresses at all:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/fc349972f6b7509b5b2459bf3bb44419961f0bcd.jpeg)

TCP, UDP, and a number of other protocol stacks are written to use IP addresses.  Routers depend on IP addresses, as we've already seen. This creates a bit of a conundrum: How do we map between MAC and IP addresses, and what does the mapping?  Is it a layer 2 or layer 3 operation?

The first thing to remember is that the MAC address is "ROM-burned" into the NIC card.  IP addresses, on the other hand, are assigned to a NIC by a DHCP server or an administrator.  This intentional separation of addressing schemes is what makes the Internet flexible.

### Fixed versus assigned addressing

Here's an analogy.  Your postal address doesn't /actually/ define where your house is located.  There are two layers of other addressing schemes that are actually used by government organisations, like your county tax assessor or the local air ambulance company.

One is your land survey location.  Depending on where you live, this is defined by a series of coordinates that go something like this: county, township, section, plat, lot, etc.  If you've ever looked at your property tax bill, it will have your postal address on it, but it will not actually use your postal address to define the taxable property.  Instead, it uses this unique set of (rather obscure) coordinates to place you exactly on land survey maps.

But that's not good enough for the air ambulance, for two reasons.  First, the survey maps are huge, complex, and hard to interpret, and they change somewhat as property is bought or sold.  Second, helicopter navigation is intentionally independent of political boundaries.  Instead, the air ambulance will use your latitude and longitude, which allows them to uniquely locate you on the earth.  Granted, the ambulance company has a tool somewhere that automatically does the maths of translating your postal address to lat/long coordinates, but the principle holds.

In terms of your local network, each of these "address levels" applies.  Your postal address corresponds to the IP address of a machine.  That IP address may or may not be unique, depending on the domain.  For example, you can use Google Maps to try and locate something like "20 Main Street", and you'll get a really long list of responses that vary by city.

Likewise, there are probably hundreds of thousands of local networks using addresses in the "192.168...." subnet, since it's so common for local IP addressing.  As mentioned above, routers at the network layer take care of protecting these unique local addresses when going out on the Internet. On the other hand, your NIC's MAC address is like the GPS lat/long coordinates; it's unique across the entire world.

What about the analogue of survey maps?  Well, it's not hard to argue that these are more like the MAC addresses that you assign to your VMs.  Every county in a state like, say, Mississippi has the coordinates Township 1, Section 1, Parcel 1 -- but the outer domain (the county) makes those coordinates unique.  Granted, we don't use a different format for MAC addresses for VMs than we do for Internet-connected NICs, but you get the idea.

### Address resolution

Address resolution is what we call the process of mapping between IP addresses and MAC addresses.  It's done with something called ARP, which stands for "Address Resolution Protocol".  Oddly enough, ARP takes on a life of its own, so you may hear it discussed in unusual ways.  Some people call it "the ARP", others speak of "arpd" (the ARP daemon), although if you look at [the man page for arpd](https://linux.die.net/man/8/arpd)**^**, you'll see those characterisations are not precisely correct.

A frequent question is, "Where does ARP take place?"  Maybe the better question is, "Where is ARP implemented?"  As always with Internet-related things, the answer can vary, but normally, ARP is implemented as part of the embedded code in the NIC.  Technically, this means that ARP operates at Layer 2.  More often, you'll see vendors hedge their bets on this, with phrases such as "operates below the Network Layer", as in [this explanation](https://support.hpe.com/hpesc/public/docDisplay?docId=emr_na-c00686597)**^**.

In reality, in order to work correctly, ARP has to map IP and MAC addresses, since the ARP message looks something like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/1/18a95f7ed64b83ec1302c92e41696d137783e7bc.jpeg)

To better understand, let's walk an ARP call.  It begins in say, a Web browser, when the browser makes a call to parse the URL.  In most cases, that URL contains a hostname (not an IP address), so the following sort of dance takes place:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/1/1365006a1692e4788df733c58e1435e67da57536.jpeg)

We won't go into this in much detail now, just know that the browser is able to gather an IP address, if it exists.  To make the walk-through less confusing, let's assume that we're looking for a host with IP 192.168.17.4.

Next, the browser requests a connection with 192.168.17.4, using the TCP protocol, which sends a connection request, as an IP packet, to 192.168.17.4.  Along the way, there is probably more than one router hop.  

ARP sends a broadcast request to everything on the relevant subnet.  This request looks like the ARP message above, but it's encoded as a MAC frame, which helps to answer the often-fuzzy question, "Is ARP Layer 2 or Layer 3?"  As you see, this is an L2 message.  Incidentally, ARP only works as a broadcast, by the way; that is, it only works on a broadcast network.

A very important note for some systems like MAAS: ARP requests don't typically span VLANs.  

Essentially, this ARP message contains the IP address 192.168.17.4, but no corresponding MAC address in the message.  This tells the owner of 192.168.17.4 that it should reply with a similar ARP message, including its MAC address.  When the sender receives the ARP reply, it can send the datagram directly to the destination host, embedded in an Ethernet frame, using the MAC address.

By the way, for efficiency, the sending host and the intermediate routers are all doing ARP caching.  They copy down the mapping between IP and MAC addresses, holding onto it for about twenty minutes.  In terms of most network transactions, twenty minutes is an eternity.

#### Messages are sent to MAC addresses

We often speak of TCP/IP as if messages are sent from one IP address to another, but that's actually not strictly true.  Messages are sent to MAC addresses.  IP addresses are only used to get MAC addresses, so the message can go through.

We can return to the air ambulance company to see a practical analogy.  A 911 call comes in for "20 Main Street, Yourtown, Yourstate, Yourpostalcode".  The address is sent to the pilot of the helicopter, who punches the address into his GPS.  The GPS uses the postal address to retrieve the lat/long coordinates, which are then used to guide the helicopter, via satellite navigation.

The same sort of thing happens when you use the GPS navigator in your car.  The navigator is translating a logical (postal) address to a physical (lat/long) address on the surface of the earth, calculating a route, and translating that route back to logical landmarks (street names) to let you know how to get there.

By the way, You should also note that ARP only works with IPv4.  Certain other protocols, like Point-to-Point Protocol (PPP), don't make use of ARP at all.

#### The ARP frame

ARP sends requests as an Ethernet frame, using the MAC address.  If you remember the MAC frame from earlier:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/1/14f6847ed92339061eb4515c12ac2b6117d5cd7c.jpeg)

The ARP frame is just a special case of the MAC frame, replacing everything the DSAP, SSAP, control bits, and data with the ARP message shown above.  The resulting ARP frame looks something like this:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/f430da9c144bda4cf2e2901181988f3444d335f8.jpeg)

Based on the above diagram, you can see how the ARP request fits into the Ethernet frame to make an ARP frame.

#### The ARP cache

Let's take a look at the ARP cache on a local system, ~cloudburst~. We can do that like this:

```nohighlight
stormrider@cloudburst:~$ arp
Address                  HWtype  HWaddress           Flags Mask            Iface
192.168.1.24             ether   0c:8b:7d:f1:51:d3   C                     wlo1
10.250.204.17                    (incomplete)                              mpqemubr0
192.168.1.24             ether   0c:8b:7d:f1:51:d3   C                     enx606d3c645a57
192.168.117.16                   (incomplete)                              virbr0
```

The columns are mostly obvious, but just in case:

- **Address**: the IP address that's been cached.
- **HWtype**: the Hardware Type field, which is blank when there's no MAC address (as is the case in a number of these entries).
- **HWaddress**: the MAC address of the device.  The "incomplete" entries are meant to indicate that an ARP request was sent for that address, but no response was received.
- **Flags Mask**: this field can have three values: "C" indicates that ARP learned this on its own, based on ARP responses; "M" means that the data was manually entered in the ARP table by a user; and "P" means "Publish," which just tells the host how to respond to incoming ARP packets.
- **Iface**: the interface name.

In this case, ~virbr0~ and ~mpqemubr0~ are virtual bridges used for different sets of libvirsh VMs that haven't been used for anything in a while. Also note that something called ~lxdbr0~, which is an LXD bridge, doesn't even show up.

Let's see if we can influence that.  First, let's take a look using ~ip a~:

```nohighlight
stormrider@cloudburst:~$ ip a show up
5: virbr0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default qlen 1000
    link/ether 52:54:00:d6:70:6c brd ff:ff:ff:ff:ff:ff
    inet 192.168.117.1/24 brd 192.168.117.255 scope global virbr0
       valid_lft forever preferred_lft forever
6: mpqemubr0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default qlen 1000
    link/ether 52:54:00:84:0a:4c brd ff:ff:ff:ff:ff:ff
    inet 10.250.204.1/24 brd 10.250.204.255 scope global mpqemubr0
       valid_lft forever preferred_lft forever
7: lxdbr0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN group default qlen 1000
    link/ether 00:16:3e:e4:2b:fe brd ff:ff:ff:ff:ff:ff
    inet 10.90.195.1/24 scope global lxdbr0
       valid_lft forever preferred_lft forever
    inet6 fd42:1fc6:f588:d0b8::1/64 scope global 
       valid_lft forever preferred_lft forever
```

You'll see that all three bridges are in a DOWN state, and again, ~lxdbr0~ is so cold that it doesn't even show up in the ARP table.  Let's bring up a LXD VM connected to ~lxdbr0~ and look at the ARP table again:

```nohighlight
stormrider@cloudburst:~$ arp
Address                  HWtype  HWaddress           Flags Mask            Iface
192.168.1.24             ether   0c:8b:7d:f1:51:d3   C                     wlo1
10.250.204.17                    (incomplete)                              mpqemubr0
192.168.1.24             ether   0c:8b:7d:f1:51:d3   C                     enx606d3c645a57
192.168.117.16                   (incomplete)                              virbr0
10.90.195.16             ether   00:16:3e:fc:71:98   C                     lxdbr0
```

Note that the ~lxdbr0~ bridge now shows up and has a MAC address, too -- no incomplete entry here.  If we look at the MAC address of ~lxdbr0~ in the ~ip~ listing, we'll see it matches up.

Those "(incomplete)" entries are old.  They've been cached, but no traffic has passed through those bridges in a really long time.  The cache is just persistent in holding onto the IP addresses, but not the MAC addresses (since they could be stale).  We can prove this to ourselves by clearing the cache:

```nohighlight
stormrider@cloudburst:~$ sudo ip -s neigh flush all
[sudo] password for stormrider: 

*Round 1, deleting 18 entries ***
*Flush is complete after 1 round ***
```

...and rebuilding the ARP table:

```nohighlight
stormrider@cloudburst:~$ arp
Address                  HWtype  HWaddress           Flags Mask            Iface
192.168.1.24             ether   0c:8b:7d:f1:51:d3   C                     wlo1
192.168.1.24             ether   0c:8b:7d:f1:51:d3   C                     enx606d3c645a57
10.90.195.16             ether   00:16:3e:fc:71:98   C                     lxdbr0
```

#### More about ARP

Another form of ARP is promiscuous ARP, in which some proxy host pretends to be the destination host and provides an ARP response on behalf of the actual destination host.  You shouldn't use this form of ARP unless there's no other choice.  You can Google it (and use it at your own risk), but it won't be described here.

There is also gratuitous ARP, when the source and destination IP addresses are the same.  This can be used for at least two purposes:

1. To find out if someone else already has the source machine's IPv4 address, a technique called Address Conflict Detection by some references.

2. To update the source machine's new MAC address (e.g., a new NIC card was installed) in upstream ARP cache entries.  This is something akin to pre-caching MAC addresses before they're actually needed.

You can [read more about](https://en.wikipedia.org/wiki/Address_Resolution_Protocol)**^** these (and many more) nuances of ARP, but this introduction should answer most of the immediate questions. 

## TCP

If the Internet Protocol (IP) is connectionless, the transport layer is all about connections.  The transport-layer protocol in use -- we'll talk exclusively about Transmission Control Protocol or TCP here -- the L4 protocol is the last place in the stack where the entire message exists in one piece.  L4 breaks up larger messages into segments.  Each segment gets a TCP header, and gets passed on to L3 where it becomes an IP packet.

### The TCP header

Here's a diagram of the L4-to-L3 hand-off:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/a/a8f2aba29b1299bba2630177c0301dd518cacb57.jpeg)

We can get a pretty good idea what happens at Layer 4 just by decoding the contents of the TCP header. It contains the following fields:

- **Source port**: the application port number of the host sending the data.  For example, if this is an FTP message, the source port would probably be 21.

- **Destination port**: the port number of the application requested on the destination host.  If this is FTP, again this port would likely be 21.

- **Sequence number**: the sequence number of this segment of data, to help the other end put the data back together in the correct order, as well as help Level 4 on the receiving end know whether a packet's been dropped or lost.

- **Acknowledgement number**: essentially, the next sequence number the destination host is expecting; used to "gate" packets through the connection.

- **TCP header length**: given to know where the data begins.

- **Reserved**: reserved for future use, basically; currently always set to 0.

- **Code bits**: essentially a set of flags; see the list below.

- **Window**: used to negotiate the "window" size, that is, how many bytes the destination host is willing to receive at once; this allows for the most efficient transmission possible, based on the characteristics of the two communicating hosts.

- **Checksum (CRC)**: used to check the integrity of the segment.

- **Urgent pointer**: data byte count where urgent data ends; used if the urgent flag is set (see below).


The code bits can indicate the following things:

- **URG**: indicates that the urgent pointer field is meaningful, used to prioritise this message over other messages.

- **ACK**: used to acknowledge successful delivery of the previous segment.

- **PSH**: push notification; tells the receiving host the message is complete, you can push the data to the application.

- **RST**: request a connection reset when the error level reaches a certain threshold; basically, "let's try that again from the top."  This is considered an abnormal termination of the TCP connection.

- **SYN**: used for a three-way TCP handshake; this handshake is how sender and receiver sync up; it serves a purpose similar to the preamble in a MAC frame, but at a different level of synchronisation.

- **FIN**: we're done, close the connection.  This is considered a normal termination of a TCP connection.

- **NS/CWR/ECE**: used to provide Explicit Congestion Notification; note that OSI provides several methods for endpoints to know that the network is congested.

### TCP is like a phone call

As you can see from the bytes above, TCP is all about the state of a connection, which is basically the same as a phone call.  When you pick up the receiver, you and the caller exchange information.  You say "bye" when the call is over.  If it's a bad connection or one end suddenly gets noisy (think jack-hammers outside), one of you can reset the connection by saying, "Let me call you back in a minute."  Take a minute and try to see how the other header bytes fit this analogy.

Also like a telephone call, TCP provides a connection (the call, however long it lasts), flow control (provided by the two parties on the call), multiplexing (handled by the two handsets, basically letting through multiple frequencies and sounds, so that you can get the tone and breath sounds of the other person, not just their raw words).  Likewise, the two parties try to handle the reliability of the connection by making sure you understand each other.

The analogy spreads a little because some of the items (connection, multiplexing) are handled by the telephone, and some are handled by the people operating the telephone (flow control, reliability).  In the network, the Level 4 protocol stack handles it all.

There is a lot more to know about TCP, but most of it isn't directly relevant for MAAS networking.  Instead, we direct you to the excellent [Wikipedia article about TCP](https://en.wikipedia.org/wiki/Transmission_Control_Protocol)**^**.  Going forward, we'll only bring up specific transport layer elements as we need them.

## DNS

Because IP addresses are hard for humans to remember, the Internet supports the use of host names to identify hosts.  These host names are associated with the host's actual IP address in a server known as a Domain Name server.  The overall protocol is known as the [Domain Name System](https://en.wikipedia.org/wiki/Domain_Name_System)**^**.