//go:build ignore

#include "vmlinux.h"
#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>

#define UDP_PROTO 0x11
#define ETH_PROTO_IP 0x0800
#define ETH_PROTO_IPV6 0x86DD
#define DHCP_PORT 67
#define MAX_PKT_BYTES 16384
// minimum packet size is 576 bytes, there is no default max, but 1500 is the average MTU
// and 64 bytes of metadata plus this is more than enough for that will evenly fitting
// into the ringbuffer
#define MAX_DHCP_PKT_SIZE 1984

struct dhcp_data {
    __u32 iface_idx;
    u8 src_mac[6];
    __u16 src_port;
    __u32 src_ip4;
    struct in6_addr src_ip6;
    u8 dhcp_pkt[MAX_DHCP_PKT_SIZE];
};

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, MAX_PKT_BYTES);
    __type(value, struct dhcp_data);
} dhcp_queue SEC(".maps");

static __always_inline int parse_dhcp_pkt(struct xdp_md *ctx, struct dhcp_data *data) {
    void *payload_end = (void *)(long)ctx->data_end;
    void *payload_data = (void *)(long)ctx->data;

    data->iface_idx = ctx->ingress_ifindex;

    struct ethhdr *eth = payload_data;
    if ((void *)(eth + 1) > payload_end) {
        return 0;
    }

    if (eth->h_proto == bpf_htons(ETH_PROTO_IP)) {
        struct iphdr *ip = (void *)(eth + 1);
        if ((void *)(ip + 1) > payload_end) {
            return 0;
        }

        if (ip->protocol != (u8)(UDP_PROTO)) {
            return 0;
        }

        struct udphdr *udp = (void *)(ip + 1);
        if ((void *)(udp + 1) > payload_end) {
            return 0;
        }

        if (udp->dest != (__u16)(bpf_htons(DHCP_PORT))) { // TODO also check for relay port
            return 0;
        }

        void *dhcp_pkt = (void *)(udp + 1);
        if (dhcp_pkt + 1 > payload_end) {
            return 0;
        }

        data->src_mac[0] = eth->h_source[0];
        data->src_mac[1] = eth->h_source[1];
        data->src_mac[2] = eth->h_source[2];
        data->src_mac[3] = eth->h_source[3];
        data->src_mac[4] = eth->h_source[4];
        data->src_mac[5] = eth->h_source[5];
        data->src_ip4 = ip->saddr;
        data->src_port = bpf_htons(udp->source);

        for (int i = 0; dhcp_pkt + i < payload_end; i++) {
            if (i >= MAX_DHCP_PKT_SIZE) {
                return 0;
            }

            data->dhcp_pkt[i] = *((u8*)(dhcp_pkt + i));
        }

        return 1;
    } else if (eth->h_proto == bpf_htons(ETH_PROTO_IPV6)) {
        struct ipv6hdr *ip6 = (void *)(eth + 1);
        if ((void *)(ip6 + 1) > payload_end) {
            return 0;
        }

        if (ip6->nexthdr != (u8)(UDP_PROTO)) {
            return 0;
        }

        struct udphdr *udp = (void *)(ip6 + 1);
        if ((void *)(udp + 1) > payload_end) {
            return 0;
        }

        if (udp->dest != (__u16)(bpf_htons(DHCP_PORT))) {
            return 0;
        }

        void *dhcp_pkt = (void *)(udp + 1);
        if (dhcp_pkt + 1 > payload_end) {
            return 0;
        }
        
        data->src_mac[0] = eth->h_source[0];
        data->src_mac[1] = eth->h_source[1];
        data->src_mac[2] = eth->h_source[2];
        data->src_mac[3] = eth->h_source[3];
        data->src_mac[4] = eth->h_source[4];
        data->src_mac[5] = eth->h_source[5];
        data->src_ip6 = ip6->saddr;
        data->src_port = bpf_htons(udp->source);
        
        for (int i = 0; dhcp_pkt + i < payload_end; i++) {
            if (i >= MAX_DHCP_PKT_SIZE) {
                return 0;
            }

            data->dhcp_pkt[i] = *((u8*)(dhcp_pkt + i));
        }
        
        return 1;
    }
        
    return 0;
}

SEC("xdp")
int xdp_prog_func(struct xdp_md *ctx) {
    struct dhcp_data *data;

    data = bpf_ringbuf_reserve(&dhcp_queue, (__u64)sizeof(struct dhcp_data), 0);
    if (!data) {
        // if we fail to store the packet data, allow it to continue its normal path
        return XDP_PASS;
    }

    if (!parse_dhcp_pkt(ctx, data)) {
        bpf_ringbuf_discard(data, 0);
        return XDP_PASS; // let anything non-DHCP continue as normal
    }

    bpf_ringbuf_submit(data, 0);

    return XDP_DROP; // the packet has been read into the queue, it's now ok to drop it
}

