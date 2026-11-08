/* Fake controller bus; never reads/writes physical MMIO. */
#include "ranked_usb_device.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t memory[0x20000/4];
static struct { uintptr_t address; uint32_t value; } writes[4096];
static unsigned nwrites;
static bool include_status;
static uint8_t firmware[0x20000],led_data[8];
static unsigned completed,configured_calls;
static unsigned packets_received;
static uint8_t received[64];
static void packet(void *c,unsigned ep,const uint8_t *p,uint16_t n){
    (void)c;assert(ep==RANKED_USB_RAW_OUT_ENDPOINT);assert(n==RANKED_USB_RAW_REPORT_BYTES);
    memcpy(received,p,n);packets_received++;
}
static uint8_t rd8(void *c,uintptr_t a){(void)c;assert(a>=0x40000000u&&a<0x40020000u);return ((uint8_t*)memory)[a-0x40000000u];}
static uint32_t rd32(void *c,uintptr_t a){(void)c;assert(a>=0x40000000u&&a<0x40020000u&&!(a&3u));return memory[(a-0x40000000u)/4];}
static void wr32(void *c,uintptr_t a,uint32_t v){(void)c;assert(a>=0x40000000u&&a<0x40020000u&&!(a&3u));memory[(a-0x40000000u)/4]=v;assert(nwrites<4096);writes[nwrites].address=a;writes[nwrites++].value=v;}
static const uint8_t *descriptor(void *c,uint8_t type,uint8_t idx,uint16_t iface,uint16_t *n){
    (void)c;unsigned a=0;*n=0;
    if(type==1){a=0x104a7;*n=18;}
    if(type==2){a=0x104b9;*n=66;}
    if(type==0x22){a=iface?0x10540:0x104ff;*n=iface?211:65;}
    if(type==0x21){a=iface?0x104e4:0x104cb;*n=9;}
    if(type==3&&idx<4){static const unsigned x[]={0x104fb,0xf5c7,0xf5d5,0xf5f9};a=x[idx];*n=firmware[a];}
    return a?firmware+a:NULL;
}
static void config(void *c,uint8_t n){(void)c;assert(n<=1);configured_calls++;}
static bool control(void *c,const ranked_usb_setup *s,ranked_usb_control_reply *r){
    (void)c;if(s->request_type==0x21&&s->request==9){r->out_data=led_data;r->out_capacity=sizeof led_data;return true;}return false;
}
static void complete(void *c,const ranked_usb_setup *s,const uint8_t *p,uint16_t n){(void)c;if(s->request_type==0x21){assert(p==led_data&&n==1&&p[0]==2);completed++;}}
static void set_event(ranked_usb_device *d,unsigned event){memory[0x16000/4]=event;memory[0x16008/4]=1;ranked_usb_device_irq(d);}
static void setup_event(ranked_usb_device *d,const uint8_t packet[8]){for(unsigned i=0;i<8;i++)memory[(0x17fa0+4*i)/4]=packet[i];set_event(d,0);}
static void print_writes(void){putchar('[');bool first=true;for(unsigned i=0;i<nwrites;i++)if(include_status||writes[i].address!=0x40016008u){printf("%s[\"0x%08lx\",%lu]",first?"":",",(unsigned long)writes[i].address,(unsigned long)writes[i].value);first=false;}putchar(']');}
int main(int argc,char **argv){
    assert(argc==3);FILE *f=fopen(argv[1],"rb");assert(f);assert(fread(firmware,1,sizeof firmware,f)==sizeof firmware);fclose(f);
    ranked_usb_bus bus={NULL,rd8,rd32,wr32,NULL};
    ranked_usb_callbacks cb={0};cb.descriptor=descriptor;cb.configured=config;cb.control=control;cb.control_complete=complete;cb.packet=packet;
    ranked_usb_device d;ranked_usb_device_init(&d,&bus,&cb);
    if(!strcmp(argv[2],"trace_init")){include_status=true;print_writes();putchar('\n');return 0;}
    if(!strcmp(argv[2],"trace_event4")||!strcmp(argv[2],"trace_event4_outer")){
        include_status=!strcmp(argv[2],"trace_event4_outer");
        memset(memory,0,sizeof memory);nwrites=0;d.configuration=1;
        d.phase=RANKED_EP0_IN_DATA;d.apply_address=true;d.need_zlp=true;
        d.remote_wakeup=true;d.pending_address=9;d.address=7;
        d.transferred=8;d.total=18;d.reply.data=firmware;
        for(unsigned ep=0;ep<6;ep++)d.ready[ep]=false;
        memory[0x17f78/4]=0x81;memory[0x17f7c/4]=0x45;set_event(&d,4);
        assert(d.configuration==0&&configured_calls==1&&d.phase==RANKED_EP0_IDLE);
        assert(!d.apply_address&&!d.need_zlp&&!d.remote_wakeup);
        assert(!d.address&&!d.pending_address&&!d.transferred&&!d.total&&!d.reply.data);
        for(unsigned ep=0;ep<6;ep++)assert(d.ready[ep]);
        print_writes();putchar('\n');return 0;
    }
    if(!strncmp(argv[2],"trace_aux_",10)){
        memset(memory,0,sizeof memory);nwrites=0;
        memory[0x17f58/4]=(uint32_t)strtoul(argv[2]+10,NULL,16);
        ranked_usb_device_aux_irq(&d);print_writes();putchar('\n');return 0;
    }
    if(!strcmp(argv[2],"trace_reset")){
        memset(memory,0,sizeof memory);nwrites=0;d.configuration=1;
        memory[0x17f58/4]=0x08;memory[0x16008/4]=2;ranked_usb_device_irq(&d);
        assert(!ranked_usb_device_configured(&d)&&configured_calls==1);
        print_writes();putchar('\n');return 0;
    }
    if(!strcmp(argv[2],"trace_raw_out")){
        memset(memory,0,sizeof memory);nwrites=0;
        for(unsigned i=0;i<32;i++)memory[(0x17500+i*4)/4]=0xdeadbe80u+i;
        memory[0x17f2c/4]=32;set_event(&d,13);
        assert(packets_received==1);
        for(unsigned i=0;i<32;i++)assert(received[i]==0x80u+i);
        print_writes();putchar('\n');return 0;
    }
    if(!strcmp(argv[2],"trace_raw_in")){
        memset(memory,0,sizeof memory);nwrites=0;d.configuration=1;
        for(unsigned i=0;i<32;i++)received[i]=(uint8_t)(0x80u+i);
        assert(ranked_usb_device_send(&d,RANKED_USB_RAW_IN_ENDPOINT,received,32));
        print_writes();putchar('\n');return 0;
    }
    if(!strcmp(argv[2],"trace_descriptor")){
        memset(memory,0,sizeof memory);nwrites=0;
        const uint8_t p[]={0x80,6,0,1,0,0,18,0};
        putchar('[');setup_event(&d,p);print_writes();
        for(unsigned i=0;i<3;i++){nwrites=0;set_event(&d,6);putchar(',');print_writes();}
        nwrites=0;memory[0x17f14/4]=0;set_event(&d,7);putchar(',');print_writes();puts("]");return 0;
    }
    if(!strcmp(argv[2],"trace")){
        const uint8_t packets[][8]={{0,5,7,0,0,0,0,0},{0,9,1,0,0,0,0,0},{0,9,0,0,0,0,0,0},{0,5,128,0,0,0,0,0}};
        putchar('[');
        for(unsigned k=0;k<4;k++){
            ranked_usb_device_init(&d,&bus,&cb);memset(memory,0,sizeof memory);nwrites=0;
            if(k)putchar(',');
            setup_event(&d,packets[k]);putchar('[');print_writes();nwrites=0;
            set_event(&d,6);putchar(',');print_writes();putchar(']');
        }
        puts("]");return 0;
    }
    const struct {uint8_t packet[8];unsigned offset,length;} requests[]={
        {{0x80,6,0,1,0,0,8,0},0x104a7,8},{{0x80,6,0,1,0,0,18,0},0x104a7,18},
        {{0x80,6,0,2,0,0,255,0},0x104b9,66},{{0x81,6,0,0x22,0,0,255,0},0x104ff,65},
        {{0x81,6,0,0x22,1,0,255,0},0x10540,211},{{0x80,6,1,3,9,4,255,0},0xf5c7,14}
    };
    for(unsigned k=0;k<sizeof requests/sizeof *requests;k++){
        uint8_t got[512];unsigned total=0;setup_event(&d,requests[k].packet);
        for(unsigned guard=0;guard<100;guard++){
            if(d.phase==RANKED_EP0_OUT_STATUS)break;
            assert(d.phase==RANKED_EP0_IN_DATA);unsigned n=memory[0x17ed4/4];assert(n<=8);
            for(unsigned i=0;i<n;i++)got[total++]=rd8(NULL,0x40017c00u+4*i);
            set_event(&d,6);
        }
        assert(total==requests[k].length);assert(!memcmp(got,firmware+requests[k].offset,total));
        memory[0x17f14/4]=0;set_event(&d,7);assert(d.phase==RANKED_EP0_IDLE);
    }
    const uint8_t address[]={0,5,7,0,0,0,0,0};setup_event(&d,address);assert(d.address==0);set_event(&d,6);assert(d.address==7);
    const uint8_t configuration[]={0,9,1,0,0,0,0,0};setup_event(&d,configuration);set_event(&d,6);assert(ranked_usb_device_configured(&d));
    uint8_t report[8]={0,0,4};assert(ranked_usb_device_send(&d,1,report,8));assert(!ranked_usb_device_send(&d,1,report,8));set_event(&d,8);assert(ranked_usb_device_send(&d,1,report,8));
    const uint8_t led[]={0x21,9,0,2,0,0,1,0};setup_event(&d,led);assert(d.phase==RANKED_EP0_OUT_DATA);
    memory[0x17b00/4]=2;memory[0x17f14/4]=1;set_event(&d,7);assert(d.phase==RANKED_EP0_IN_STATUS);set_event(&d,6);assert(completed==1);
    for(unsigned i=0;i<32;i++)memory[(0x17500+i*4)/4]=0xdeadbe80u+i;
    memory[0x17f2c/4]=32;set_event(&d,13);assert(packets_received==1);
    for(unsigned i=0;i<32;i++)assert(received[i]==0x80u+i);
    assert(memory[0x17f2c/4]==127);
    assert(ranked_usb_device_send(&d,RANKED_USB_RAW_IN_ENDPOINT,received,32));
    assert(memory[0x17ee4/4]==32);
    for(unsigned i=0;i<32;i++)assert(memory[(0x17800+i*4)/4]==received[i]);
    assert(!ranked_usb_device_send(&d,RANKED_USB_RAW_IN_ENDPOINT,received,32));
    set_event(&d,10);assert(ranked_usb_device_send(&d,RANKED_USB_RAW_IN_ENDPOINT,received,32));
    puts("Control engine descriptors, status stages, LED OUT, raw32-byteep3RX/ep2TX and readiness checks passed");
    return 0;
}
