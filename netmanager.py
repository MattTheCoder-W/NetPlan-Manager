#!/usr/bin/sudo /usr/bin/python3

# Autor: Mateusz Wasążnik
# Data: 25.05.2021
# Działanie: Program pozwala na pracę z plikiem netplan w sposób zautomatyzowany oraz przejrzysty dla użytkownika
# System: Linux (Ubuntu 18/20)
# Status: Ukonczone

import os
import sys
import time
import keyboard
import subprocess
from getch import getch
from curtsies.fmtfuncs import red, bold, green, on_blue, yellow, blue, cyan


if os.name != "posix":
    print("Ten program działa tylko na systemach typu Linux")
    exit()
if os.geteuid() != 0:
    # print("Uruchom ten program jako root!!!")
    p = subprocess.Popen(["sudo", "-s", "whoami"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    p.kill()

w, h = list(os.get_terminal_size())
VERBOSE = False

def ask(title, options, default=0, fill=2):
    if not options:
        return None
    out = None
    print(title)
    for i, option in enumerate(options):
        print(f"{str(i).zfill(fill)} >> {option}")
    while True:
        choice = input(f"[{default}]-> ")
        if choice:
            if choice.isnumeric():
                try:
                    out = options[int(choice)]
                    break
                except KeyError:
                    print("Podaj wartość z zakresu!")
            else:
                print("Podaj wartość liczbową!")
        else:
            out = options[default]
            break
    return out

IP, MASK, YESNO = [0, 1, 2]
def askfordata(prefix, typ=IP):
    out = None
    while True:
        out = input(f"{prefix} -> ")
        if out:
            if typ == IP:
                if out.count(".") == 3:
                    oktety = out.split(".")
                    oktety_out = []
                    for oktet in oktety:
                        if not oktet.isnumeric() or int(oktet) > 255:
                            oktety = None
                            break
                        else:
                            oktety_out.append(str(int(oktet)))
                    if oktety is None:
                        print("Proszę podać właściwy adres!")
                        continue
                    else:
                        out = '.'.join(oktety_out)
                        return out
                else:
                    print("Adres IP składa się z 4 oktetów odzielonych kropkami ;)")
            elif typ == MASK:
                out = out.replace("/", "")
                if out.isnumeric() and len(str(out)) == 2 and int(out) <= 30:
                    return str(int(out))
                else:
                    print("Proszę podać właściwy numer maski!")
            elif typ == YESNO:
                if out.lower() in ['y', 'n']:
                    return True if out.lower() == "y" else False
                else:
                    print("Oczekiwano y/n!")
            else:
                return None
        else:
            return None


def contains(search, lst):
    return [i for i, x in enumerate(lst) if search in x]


def check_interest(interest, data):
    for elem in data:
        if elem in range(interest[0], interest[1]+1):
            return elem
    return None


class NetPlan:
    def __init__(self, inter, filepath):
        self.inter = inter
        self.file = filepath
        self.content = None
    
    def backup(self):
        os.system(f"sudo cp {self.file} {self.file}.bak")
        print(f"Wykonano kopię zapasową: {self.file}.bak")

    def create(self, out=None):
        if out is None:
            out = self.file
        init_lines = ['network:',
                '\tversion: 2',
                '\trenderer: NetworkManager']

        with open(out, "w") as f:
            for line in init_lines:
                line = line.replace("\t", "  ")
                f.write(line+"\n")

    def interactive(self):
        active = 0
        options = [['Adres IP', '___.___.___', IP],
                ['Maska Sieci', '/__', MASK],
                ['Adres Bramy', '___.___.___', IP],
                ['DHCP?', '___', YESNO]]
                
        
        for opt in options:
            tabs = '\t' if len(opt[0]) > 6 else '\t\t'
            print(f"{opt[0]}:{tabs}{opt[1]}")
        for i, opt in enumerate(options):
            if i == 1 and options[0][1] is None:
                continue
            answ = askfordata(opt[0], typ=opt[2])
            opt[1] = answ
            print("\n"*h)
            for o in options:
                tabs = '\t' if len(o[0]) > 6 else '\t\t'
                print(f"{o[0]}:{tabs}{o[1]}")
        
        output = [opt[1] for opt in options]
        return output

    def load(self):
        with open(self.file, "r") as f:
            self.content = [x.replace("  ", "\t").replace("\n", "") for x in f.readlines()]

    def insert_conf(self, options, delrest = False):
        self.load()
        if not contains("\tethernets:", self.content):
            self.content.append("\tethernets:")
        if not contains(f"\t\t{self.inter}", self.content):
            self.content.append(f"\t\t{self.inter}:")

        interest = [contains(f"\t\t{self.inter}:", self.content)[0], -1]
        for i in range(interest[0]+1, len(self.content)):
            if self.content[i].count("\t") == 2:
                interest[1] = i-1
                break
        if interest[1] == -1:
            print("WARN")
            interest[1] = len(self.content)-1

        todel = []

        addr_check = contains("\t\t\taddresses:", self.content)
        if not addr_check:
            addr_line = -1
        elif check_interest(interest, addr_check):
            addr_line = check_interest(interest, addr_check)
        else:
            addr_line = -1
        
        gateway_check = contains("\t\t\tgateway4:", self.content)
        if not gateway_check:
            gateway_line = -1
        elif check_interest(interest, gateway_check):
            gateway_line = check_interest(interest, gateway_check)
        else:
            gateway_line = -1

        dhcp_check = contains("\t\t\tdhcp4:", self.content)
        if not dhcp_check:
            dhcp_line = -1
        elif check_interest(interest, dhcp_check): 
            dhcp_line = check_interest(interest, dhcp_check)
        else:
            dhcp_line = -1

        if VERBOSE:
            print(self.content)
            print(interest, addr_line, gateway_line, dhcp_line)

        offset = 0
        if options[0] is not None and options[1] is not None:
            data = "\t\t\taddresses: ["+options[0]+"/"+options[1]+"]"
            if addr_line == -1:
                self.content.insert(interest[1]+1, data)
                offset += 1
            else:
                self.content[addr_line+offset] = data
        elif delrest:
            if addr_line != -1:
                todel.append(addr_line+offset)
        if options[2] is not None:
            data = "\t\t\tgateway4: " + options[2]
            if gateway_line == -1:
                self.content.insert(interest[1]+1, data)
                offset += 1
            else:
                self.content[gateway_line+offset] = data
        elif delrest:
            if gateway_line != -1:
                todel.append(gateway_line+offset)
        if options[3] is not None:
            data = "\t\t\tdhcp4: "
            data += "yes" if options[3] == True else "no"
            if dhcp_line == -1:
                self.content.insert(interest[1]+1, data)
                offset += 1
            else:
                self.content[dhcp_line+offset] = data
        elif delrest:
            if dhcp_line != -1:
                todel.append(dhcp_line+offset)

        for offst, i in enumerate(todel):
            self.content.pop(i-offst)

        if VERBOSE:
            print(self.content)

        with open(self.file, "w") as outfile:
            for line in self.content:
                outfile.write(line.replace("\t", "  ")+"\n")
        print(green("Zapisano zmiany do pliku!"))

    def show(self):
        os.system("sudo cat "+self.file)


resetMode = False
if len(sys.argv) >= 2 and sys.argv[1] == "reset":
    resetMode = True
    print(yellow("UWAGA! Jesteś w trybie resetowania konfiguracji!"))

interfaces = [x for x in os.listdir("/sys/class/net/") if x[0] != "w"]

print(yellow("UWAGA! Program opsługuje tylko interfejsy połączeń kablowych!"))

interface = ask("Wybór interfejsu:", interfaces)
if interface is None:
    print(red("Nie znaleziono interfejsów sieciowych na tym urządzeniu!"))
    exit()
print(green(f"Wybrano: {interface}"))

print("="*w)

conf_files = [x for x in os.listdir("/etc/netplan/") if not x.endswith(".bak")]
conf_file = ask("Wybór pliku konfiguracyjnego:", conf_files)
if conf_file is None:
    print("Nie znaleziono żadnej konfiguracji netplan, nowa została utworzona!")
    NetPlan.create(NetPlan, out="/etc/netplan/01-network-manager-all.yaml")
    conf_file = "01-network-manager-all.yaml"

print(green("Wybrano: " + conf_file))

if resetMode:
    pth = os.path.join("/etc/netplan", conf_file)
    os.system(f"sudo cp {pth} {pth}.bak")
    os.system(f"sudo rm {pth}")
    print(green("Usunięto wybrany plik!"))
    exit()

print("="*w)

# ops = ['192.168.0.141', '24', '192.168.0.1', None]
ops = NetPlan.interactive(NetPlan)

delrest = False
if None in ops:
    while True:
        chck = input("Czy chcesz pominięte parametry usunąć z pliku konfiguracyjnego czy zachować już występujące dane? (y/N): ")
        if chck:
            if chck.lower() in ['y', 'n']:
                delrest = True if chck.lower() == 'y' else False
                break
            else:
                print(red("Oczekiwano odpowiedzi y/n!"))
        else:
            delrest = False
            break

netplan = NetPlan(interface, os.path.join("/etc/netplan", conf_file))
netplan.backup()

netplan.insert_conf(ops, delrest = delrest)

netplan.show()

run = True
while True:
    chck = input("Czy chcesz zatwierdzić tą konfigurację? (Y/n): ")
    if chck:
        if chck.lower() in ['y', 'n']:
            run = True if chck.lower() == "y" else False
            break
    else:
        run = True
        break

if run:
    print(yellow("Wywołuję komendę: sudo netplan apply"))
    os.system("sudo netplan apply")

print("Program zakończył działanie ;)")

