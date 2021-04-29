# 使用raspberrypi 4B安装旁路由



## 1. raspberry pi 4B 安装

- 安装Raspberry Pi 4B 硬件

- 下载并安装烧写系统的PiImger

- (optional) 下载基于Debian Buster的Raspberry Pi OS Lite

- TF卡（A.K.A Micro SD）烧写Raspberry Pi OS Lite

- 连接Pi，开机

- 使用账号pi/密码raspberry登陆，之后开始准备操作

```
sudo su root
passwd

apt update
apt install ntp

# 修改IP地址为静态的192.168.31.31
nano /etc/dhcpcd_conf
# 手动写入下面四行
interface eth0
static ip_address=192.168.31.31/24
static routers=192.168.31.1
static domain_name_servers=192.168.31.1 8.8.8.8

# 设置ssh连接
# 使用下面的命令修改，或者手动 nano /etc/ssh/sshd_config 
sed -i '' 's/#Port /Port /g' /etc/ssh/sshd_config
sed -i '' 's/#AddressFamily /AddressFamily /g' /etc/ssh/sshd_config
sed -i '' 's/#ListenAddress /ListenAddress /g' /etc/ssh/sshd_config
sed -i '' 's/#PermitRootLogin.*/PermitRootLogin yes/g' /etc/ssh/sshd_config
sed -i '' 's/#PasswordAuthentication .*/PasswordAuthentication yes /g' /etc/ssh/sshd_config

# 启动ssh服务
systemctl enable ssh
systemctl start ssh

# reboot
后面可以从ssh设置了
```

 

## 2. 初步安装V2Ray

参考 https://guide.v2fly.org/app/tproxy.html

但是也可以使用https://github.com/zengyongxing/v2pi项目中的脚本

- 路由器设置DHCP参数。将网关指向192.168.31.31

  > OpenWRT>Network>Interface>Lan>HDCP Server>Advanced Settings>HDCP-Options 添加下面两行
  >
  > 3,192.168.31.31 # 指定网关
  >
  > 6,192.168.3.1,223.5.5.5 # 指定DNS，其实没有用最后都到31.31了。

- mac和pi都加入这个网络，然后开始安装

- 下载脚本

  ```
  git clone https://github.com/zengyongxing/v2pi.git
  ```

  

- (Optional)下载pi对应的v2ray软件（ARM32-v7a）

  https://github.com/v2fly/v2ray-core/releases/download/v4.38.1/v2ray-linux-arm32-v7a.zip

  到`/v2pi/script`目录

- 整个压缩v2pi目录为zip包。

- 然后开始安装到Pi

  ```
  scp v2pi.zip root@192.168.31.31:/usr/local/
  ssh root@192.168.31.31
  
  cd /usr/local
  unzip v2pi.zip
  
  cd v2pi/script
  
  # 设置pi的路由转发功能
  echo net.ipv4.ip_forward=1 >> /etc/sysctl.conf && sysctl -p
  # sysctl -p执行后将出现 net.ipv4.ip_forward=1 的提示
  # 这个时候网络里面的设备应该可以通过网关31不翻墙访问外网。
  
  # 安装V2ray
  ./install-release.sh --local v2ray-linux-arm32-v7a.zip
  
  # 使用正常的客户端json来测试是否正常
  nano /usr/local/etc/v2ray/config.json
  # 添加一个可以用的json，然后使用下面的代码测试
  systemctl enable v2ray
  systemctl restart v2ray
  curl google.com -x socks5://127.0.0.1:1080
  
  
  # 修改V2ray和iptable
  cp /usr/local/v2pi/script/v2ray.config.json /usr/local/etc/v2ray/config.json
  ./config_iptable.sh
  ./config_tproxy.sh
  systemctl restart v2ray
  
  # Done
  
  ```

  

  

  

