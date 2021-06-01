# encoding: utf-8
"""
File:       core_service
Author:     twotrees.us@gmail.com
Date:       2020年7月30日  31周星期四 10:55
Desc:
"""
import psutil
import os
import os.path
from .package import jsonpickle
from typing import List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import *
import requests
from requests.adapters import HTTPAdapter
import random
import time
import socket
import socks

from .app_config import AppConfig
from .v2ray_controller import V2rayController, make_controller
from .node_manager import NodeManager
from .keys import Keyword as K
from .v2ray_user_config import V2RayUserConfig

class CoreService:
    app_config : AppConfig = None
    user_config: V2RayUserConfig = V2RayUserConfig()
    v2ray:V2rayController = make_controller()
    node_manager:NodeManager = NodeManager()
    scheduler:BackgroundScheduler = BackgroundScheduler(
        {
            'apscheduler.executors.default': {
                'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
                'max_workers': '1'
            }
        })

    @classmethod
    def load(cls):
        config_path = 'config/'
        if not os.path.exists(config_path):
            os.mkdir(config_path)

        cls.app_config = AppConfig().load()
        cls.node_manager = NodeManager().load()
        cls.user_config = V2RayUserConfig().load()

        cls.restart_auto_detect()

    @classmethod
    def status(cls) -> dict:
        running = cls.v2ray.running()
        version = cls.v2ray.version()

        result = {
            K.running: running,
            K.version: version,
            K.proxy_mode: cls.user_config.proxy_mode,
        }

        node = cls.user_config.node.dump()
        result.update(node)
        return result

    @classmethod
    def performance(cls) -> dict:
        result = {}
        cpu_usage = psutil.cpu_percent(interval=0.2, percpu=True)
        result_cpu = {}
        core = 0
        for u in cpu_usage:
            core += 1
            result_cpu["core {0}".format(core)] = u
        result['cpu'] = result_cpu

        memory_usage = psutil.virtual_memory()
        result['memory'] = {
            "percent" : memory_usage.percent,
            "total" : int(memory_usage.total / (1024 * 1024)),
            "used" : int((memory_usage.total - memory_usage.available) / (1024 * 1024))
        }
        return result

    @classmethod
    def add_subscribe(cls, url):
        cls.node_manager.add_subscribe(url)
        cls.re_apply_node()

    @classmethod
    def remove_subscribe(cls, url):
        cls.node_manager.remove_subscribe(url)
        cls.re_apply_node()

    @classmethod
    def update_all_subscribe(cls):
        cls.node_manager.update_all()
        cls.re_apply_node()

    @classmethod
    def update_subscribe(cls, url):
        cls.node_manager.update(url)
        cls.re_apply_node()

    @classmethod
    def add_manual_node(cls, url):
        cls.node_manager.add_manual_node(url)
        cls.re_apply_node()

    @classmethod
    def delete_node(cls, url, index):
        cls.node_manager.delete_node(url, index)
        cls.re_apply_node()

    @classmethod
    def re_apply_node(cls, restart_auto_detect=True) -> bool:
        result = cls.v2ray.apply_node(cls.user_config, cls.node_manager.all_nodes())
        if restart_auto_detect:
            cls.restart_auto_detect()
        return result

    @classmethod
    def restart_auto_detect(cls):
        cls.auto_detect_cancel()
        if cls.user_config.advance_config.auto_detect.enabled :
            cls.auto_detect_start()

    @classmethod
    def stop_v2ray(cls) -> bool:
        result = cls.v2ray.stop()
        cls.auto_detect_cancel()

        return result

    @classmethod
    def apply_node(cls, url:str, index: int, restart_auto_detect=True) -> bool:
        result = False
        node = cls.node_manager.find_node(url, index)
        cls.user_config.node = node
        if cls.re_apply_node(restart_auto_detect):
            cls.user_config.save()

            if not cls.app_config.inited:
                cls.v2ray.enable_iptables()
                cls.app_config.inited = True
                cls.app_config.save()
            result = True
        return result

    @classmethod
    def switch_mode(cls, proxy_mode: int) -> bool:
        cls.user_config.proxy_mode = proxy_mode
        result = True
        result = cls.re_apply_node()
        if result:
            cls.user_config.save()

        return result

    @classmethod
    def apply_advance_config(cls, config:dict):
        result = True
        new_advance = cls.user_config.advance_config.load_data(config)
        cls.user_config.advance_config = new_advance
        result = cls.re_apply_node()
        if result:
            cls.user_config.save()
        return  result

    @classmethod
    def reset_advance_config(cls):
        result = True
        cls.user_config.advance_config = V2RayUserConfig.AdvanceConfig()
        result = cls.re_apply_node()
        if result:
            cls.user_config.save()
        return result

    @classmethod
    def make_policy(cls, contents:List[str], type:str, outbound:str) -> dict:
        type = V2RayUserConfig.AdvanceConfig.Policy.Type[type]
        outbound = V2RayUserConfig.AdvanceConfig.Policy.Outbound[outbound]
        policy = V2RayUserConfig.AdvanceConfig.Policy()
        policy.contents = contents
        policy.type = type.name
        policy.outbound = outbound.name
        return jsonpickle.encode(policy, indent=4)

    @classmethod
    def auto_detect_start(cls):
        cls.scheduler.add_job(CoreService.auto_detect_job, trigger='interval', seconds=cls.user_config.advance_config.auto_detect.detect_span, id=K.auto_detect)
        if cls.scheduler.state is not STATE_RUNNING :
            cls.scheduler.start()

    @classmethod
    def auto_detect_cancel(cls):
        job = cls.scheduler.get_job(K.auto_detect)
        if job:
            job.remove()
    
    @classmethod
    def auto_detect_job(cls):
        detect:V2RayUserConfig.AdvanceConfig.AutoDetectAndSwitch = cls.user_config.advance_config.auto_detect
        socks_port = cls.user_config.advance_config.inbound.socks_port()
        try:
            starttime = time.time()
            SOCKS5_PROXY_HOST = '127.0.0.1'		 # socks 代理IP地址
            SOCKS5_PROXY_PORT = socks_port           # socks 代理本地端口
            default_socket = socket.socket
            socks.set_default_proxy(socks.SOCKS5, SOCKS5_PROXY_HOST, SOCKS5_PROXY_PORT)
            socket.socket = socks.socksocket
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) Gecko/20100101 Firefox/62.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2"
            }
            session = requests.session()
            session.keep_alive = False
            session.mount('http://',HTTPAdapter(max_retries=detect.failed_count))#设置重试次数
            session.mount('https://',HTTPAdapter(max_retries=detect.failed_count))
            resp=session.get(detect.detect_url,headers=headers,timeout=detect.timeout)
            html_source=resp.text        
            resp.close()
            if html_source: 
                print('ok')
            else: 
                print('fail')
            endtime = time.time()
            print(endtime-starttime)
            print('detected connetion success, nothing to do, just return')
            detect.last_switch_time = '{0} ---- {1}'.format(datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'), '无需切换')
            cls.user_config.save()
            return
        except Exception as e:
            print('detected connetion failed, detail:\n{0}'.format(e))
            ping_groups = cls.node_manager.ping_test_all()

            class NodePingInfo:
                def __init__(self, group_key:str, node_ps:str, ping:int):
                    self.group_key:str = group_key
                    self.node_ps:str = node_ps
                    self.ping:int = ping

                def __lt__(self, other):
                    return self.ping < other.ping

            ping_results = []
            for group in ping_groups:
                group_key = group[K.subscribe]
                nodes = group[K.nodes]
                for node_ps in nodes.keys():
                    ping = nodes[node_ps]
                    info = NodePingInfo(group_key, node_ps, ping)
                    if ping > 0:
                        ping_results.append(info)
            
            ping_results.sort()
            if len(ping_results) > 0:
                best_node = random.choice(ping_results) # 随机抽一个
                node_index = cls.node_manager.find_node_index(best_node.group_key, best_node.node_ps)
                cls.apply_node(best_node.group_key, node_index, restart_auto_detect=False)
                detect.last_switch_time = '{0} ---- {1}'.format(datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'), best_node.node_ps)
                cls.user_config.save()
            else:
                detect.last_switch_time = '{0} ---- {1}'.format(datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'), '无节点')
                cls.user_config.save()
    