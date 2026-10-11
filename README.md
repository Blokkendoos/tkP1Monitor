# Slimme Meter monitor

Show the current consumed energy values from a HomeWizard P1 Monitor.

## HomeWizard
- local API activated
- adjust IP-address in the code

## Usage
### Create Python virtual environment
```
$ python3 -v venv
$ . venv/bin/activate
(venv) pip install python-homewizard-energy matplotlib numpy scipy
(venv) deactivate
```
### Get the code
```
$ git clone https://github.com/Blokkendoos/tkP1Monitor.git 
$ cd tkP1Monitor
$ vi slimme_meter.py
IP_ADDRESS = '192.168.178.221'  # change IP
:wq
```
### Run
```
$ . venv/bin/activate
(venv) cd tkP1Monitor
(venv) ./slimme_meter.py
(venv) deactivate
```

![Screenshot](Screenshot.png?raw=true "Screenshot")

