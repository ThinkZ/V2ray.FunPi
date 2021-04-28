#!/usr/bin/env bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

#check Root
[ $(id -u) != "0" ] && { echo "${CFAILURE}Error: You must be root to run this script${CEND}"; exit 1; }


# 开启ssh服务
echo "1: 开启ssh服务"
sed -i '' 's/#Port /Port /g' /etc/ssh/sshd_config
sed -i '' 's/#AddressFamily /AddressFamily /g' /etc/ssh/sshd_config
sed -i '' 's/#ListenAddress /ListenAddress /g' /etc/ssh/sshd_config
sed -i '' 's/#PermitRootLogin.*/PermitRootLogin yes/g' /etc/ssh/sshd_config
sed -i '' 's/#PasswordAuthentication .*/PasswordAuthentication yes /g' /etc/ssh/sshd_config
systemctl start ssh



echo "2: 下载和更新依赖库"
#install Needed Packages
apt-get update -y
apt-get install wget curl socat git python3 python3-setuptools python3-dev python3-pip openssl libssl-dev ca-certificates supervisor -y
pip3 install -r requirements.txt

#enable rc.local
cat>/etc/rc.local<<-EOF
#!/bin/sh -e
#
# rc.local
#
# This script is executed at the end of each multiuser runlevel.
# Make sure that the script will "exit 0" on success or any other
# value on error.
#
# In order to enable or disable this script just change the execution
# bits.
#
# By default this script does nothing.
if [ ! -d "/var/log/v2ray" ]; then
    mkdir /var/log/v2ray
fi
exit 0
EOF

# install v2ray
echo "3: 安装V2Ray"
mkdir -p /etc/v2ray/
touch /etc/v2ray/config.json
chmod 644 /etc/v2ray/config.json
mkdir -p /var/log/v2ray/
bash update_v2ray.sh

#configure Supervisor
echo "4: 设置supervisor和附属v2pi服务"
mkdir /etc/supervisor
mkdir /etc/supervisor/conf.d
echo_supervisord_conf > /etc/supervisor/supervisord.conf
cat>>/etc/supervisor/supervisord.conf<<EOF
[include]
files = /etc/supervisor/conf.d/*.ini
EOF
touch /etc/supervisor/conf.d/v2pi.ini
cat>/etc/supervisor/conf.d/v2pi.ini<<-EOF
[program:v2pi]
command=/usr/local/v2pi/script/start.sh run
stdout_logfile=/var/log/v2pi
autostart=true
autorestart=true
startsecs=5
priority=1
stopasgroup=true
killasgroup=true
EOF

supervisord -c /etc/supervisor/supervisord.conf
supervisorctl restart v2pi

# ip table
echo "5: 设置系统TPROXY服务:v2iptable.service"
echo net.ipv4.ip_forward=1 >> /etc/sysctl.conf && sysctl -p
cat>/etc/systemd/system/v2iptable.service<<-EOF
[Unit]
Description=Tproxy rule
After=network-online.target
Wants=network-online.target

[Service]

Type=oneshot
ExecStart=/bin/bash /usr/local/v2pi/script/config_iptable.sh

[Install]
WantedBy=multi-user.target
EOF


systemctl daemon-reload
systemctl disable v2iptable.service

# 
chmod +x /etc/rc.local
systemctl start rc-local
systemctl status rc-local



echo "install success"
