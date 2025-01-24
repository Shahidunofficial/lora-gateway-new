(.venv) vegaai@ubuntu:~/Documents/water management vega-PD/lora-gateway-new-main$ python app.py

(.venv) vegaai@ubuntu:~/Documents/water management vega-PD/lora-gateway-new-main$ ls
app.py  config.py  controller  controller_instance.py  gateway-status.json  helper  middleware  model  node-list.json  __pycache__  python_version.txt  requirements.txt  router
(.venv) vegaai@ubuntu:~/Documents/water management vega-PD/lora-gateway-new-main$ pwd
/home/vegaai/Documents/water management vega-PD/lora-gateway-new-main
(.venv) vegaai@ubuntu:~/Documents/water management vega-PD/lora-gateway-new-main$ 


(.venv) vegaai@ubuntu:~/Documents/water_management_vega_PD/lora_gateway_new_main$ /home/vegaai/Documents/water_management_vega_PD/.venv/bin/python /home/vegaai/Documents/water_management_vega_PD/lora_gateway_new_main/app.py


ORIN NX Service Monitoring
journalctl -u lora-gateway.service
systemctl status lora-gateway.service


===========

sudo nano /etc/systemd/system/lora-gateway.service

-----

[Unit]
Description=LoRa Gateway Application
After=network.target

[Service]
User=vegaai
WorkingDirectory=/home/vegaai/Documents/water_management_vega_PD/lora_gateway_new_main
ExecStart=/home/vegaai/Documents/water_management_vega_PD/.venv/bin/python /home/vegaai/Documents/water_management_vega_PD/lora_gateway_new_main/app.py
Restart=always

[Install]
WantedBy=multi-user.target

---


sudo systemctl daemon-reload

sudo systemctl enable lora-gateway.service

sudo systemctl start lora-gateway.service

sudo systemctl status lora-gateway.service

journalctl -u lora-gateway.service -f


