"""
arsenal.py - Sk7ld-AI weapon registry + intent map.

This module is the single source of truth for:

  * ARSENAL          - every tool the toolkit knows how to install (ported from
                       the Viking AI install.sh ARSENAL registry).
  * TOOL_ENTRYPOINTS - how to run a git-cloned tool (script + interpreter).
  * TOOL_DEPS        - prerequisites a tool needs before it will run.
  * NAME_ALIASES     - user-typed variants -> canonical arsenal name.
  * BIN_MAP          - canonical name -> actual binary name on PATH.
  * CATEGORIES       - category -> ordered tool names (for the arsenal browser).
  * INTENTS          - natural-language intent -> candidate ToolActions, which is
                       what powers the GUI's "which tool do you want?" dispatch.

Install-type grammar (same as the Bash engine):
    apt:<pkg>     apt-get install, git-clone fallback on failure
    pip:<pkg>     pip3 install --break-system-packages, git-clone fallback
    git_python    git clone + pip install requirements.txt
    git_go        git clone + go build
    git_generic   git clone + make / setup.sh / install.sh
"""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import List, Optional


# ════════════════════════════════════════════════════════════════════════
#  DATA MODEL
# ════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Tool:
    name: str
    category: str
    url: str
    itype: str                       # apt:pkg | pip:pkg | git_python | git_go | git_generic
    description: str = ""
    entrypoint: Optional[str] = None  # "script.py|python3"

    @property
    def install_kind(self) -> str:
        if self.itype.startswith("apt:"):
            return "apt"
        if self.itype.startswith("pip:"):
            return "pip"
        return self.itype  # git_python / git_go / git_generic

    @property
    def package(self) -> Optional[str]:
        if ":" in self.itype:
            return self.itype.split(":", 1)[1]
        return None


@dataclass
class ToolAction:
    """One concrete thing the orchestrator can offer for a detected intent."""
    tool: str                        # canonical arsenal name
    desc: str                        # short, operator-facing description
    cmd: List[str]                   # argv template, "{target}" token substituted
    mode: str = "capture"            # "capture" (stream output) | "interactive" (external term)
    needs_root: bool = False
    note: str = ""                   # optional extra guidance shown in chat


@dataclass
class Intent:
    key: str
    label: str
    pattern: str                     # regex (case-insensitive) that triggers this intent
    target_kind: str                 # target | url | domain | email | username | hash | none
    actions: List[ToolAction] = field(default_factory=list)
    _rx: Optional[re.Pattern] = None
    priority: int = 50               # lower = checked first (broad intents go last)

    def matches(self, text: str) -> bool:
        if self._rx is None:
            self._rx = re.compile(self.pattern, re.IGNORECASE)
        return bool(self._rx.search(text))


# ════════════════════════════════════════════════════════════════════════
#  ARSENAL REGISTRY  (name -> Tool)
#  Ported 1:1 from the Viking AI ARSENAL + category submenus.
# ════════════════════════════════════════════════════════════════════════
_TOOLS: List[Tool] = [
    # ── Scanning & Recon ────────────────────────────────────────────────
    Tool("WebCheck", "Scanning & Recon", "https://github.com/X3RX3SSec/WebCheck.git", "git_python", "Website security header + tech checker", "webcheck.py|python3"),
    Tool("RED_HAWK", "Scanning & Recon", "https://github.com/Tuhinshubhra/RED_HAWK.git", "git_python", "All-in-one recon, scanning & info gathering", "rhawk.php|php"),
    Tool("theHarvester", "Scanning & Recon", "https://github.com/laramies/theHarvester.git", "git_python", "Emails, subdomains & hosts from public sources", "theHarvester.py|python3"),
    Tool("spiderfoot", "Scanning & Recon", "https://github.com/smicallef/spiderfoot.git", "git_python", "Automated OSINT engine (web UI on :5001)", "sf.py|python3"),
    Tool("amass", "Scanning & Recon", "https://github.com/owasp-amass/amass.git", "apt:amass", "In-depth subdomain enumeration"),
    Tool("recon-ng", "Scanning & Recon", "https://github.com/lanmaster53/recon-ng.git", "git_python", "Modular web recon framework"),
    Tool("findomain", "Scanning & Recon", "https://github.com/findomain/findomain.git", "git_generic", "Fast cross-platform subdomain finder"),

    # ── Network Tools ───────────────────────────────────────────────────
    Tool("nmap", "Network Tools", "https://github.com/nmap/nmap.git", "apt:nmap", "The classic port scanner & service mapper"),
    Tool("masscan", "Network Tools", "https://github.com/robertdavidgraham/masscan.git", "apt:masscan", "Internet-scale asynchronous port scanner"),
    Tool("RustScan", "Network Tools", "https://github.com/bee-san/RustScan.git", "git_generic", "Ultra-fast port scanner, pipes into nmap"),
    Tool("httpx", "Network Tools", "https://github.com/projectdiscovery/httpx.git", "git_go", "Fast multi-purpose HTTP probe"),
    Tool("subfinder", "Network Tools", "https://github.com/projectdiscovery/subfinder.git", "git_go", "Passive subdomain discovery"),
    Tool("naabu", "Network Tools", "https://github.com/projectdiscovery/naabu.git", "git_go", "Fast SYN/CONNECT port finder"),
    Tool("dnsx", "Network Tools", "https://github.com/projectdiscovery/dnsx.git", "git_go", "Fast DNS toolkit / brute forcer"),

    # ── Web & Vulnerability Scanning ────────────────────────────────────
    Tool("SecretFinder", "Web Scanning", "https://github.com/m4ll0k/SecretFinder.git", "git_python", "Find API keys/secrets in JS files", "SecretFinder.py|python3"),
    Tool("waybackurls", "Web Scanning", "https://github.com/tomnomnom/waybackurls.git", "git_go", "Fetch historical URLs from Wayback Machine"),
    Tool("gau", "Web Scanning", "https://github.com/lc/gau.git", "git_go", "Get All URLs from multiple sources"),
    Tool("hakrawler", "Web Scanning", "https://github.com/hakluke/hakrawler.git", "git_go", "Fast web endpoint crawler"),
    Tool("takeover", "Web Scanning", "https://github.com/edoardottt/takeover.git", "git_go", "Subdomain takeover checker"),
    Tool("commix", "Web Scanning", "https://github.com/commixproject/commix.git", "apt:commix", "Automated command-injection exploiter"),
    Tool("wpscan", "Web Scanning", "https://github.com/wpscanteam/wpscan.git", "apt:wpscan", "WordPress vulnerability scanner"),
    Tool("ffuf", "Web Scanning", "https://github.com/ffuf/ffuf.git", "apt:ffuf", "Fast web fuzzer"),
    Tool("gobuster", "Web Scanning", "https://github.com/OJ/gobuster.git", "apt:gobuster", "Directory/DNS/vhost brute forcer"),
    Tool("dirsearch", "Web Scanning", "https://github.com/maurosoria/dirsearch.git", "apt:dirsearch", "Web path brute forcer"),
    Tool("feroxbuster", "Web Scanning", "https://github.com/epi052/feroxbuster.git", "apt:feroxbuster", "Recursive content discovery in Rust"),
    Tool("katana", "Web Scanning", "https://github.com/projectdiscovery/katana.git", "git_go", "Next-gen crawling & spidering"),
    Tool("jaeles", "Web Scanning", "https://github.com/jaeles-project/jaeles.git", "git_go", "Signature-based web scanner"),
    Tool("arjun", "Web Scanning", "https://github.com/s0md3v/Arjun.git", "pip:arjun", "HTTP parameter discovery"),
    Tool("nuclei", "Vulnerability Scanning", "https://github.com/projectdiscovery/nuclei.git", "git_go", "Template-based CVE/vuln scanner"),
    Tool("nikto", "Web Scanning", "https://github.com/sullo/nikto.git", "apt:nikto", "Classic web server vuln scanner"),

    # ── XSS Tools ───────────────────────────────────────────────────────
    Tool("dalfox", "XSS Tools", "https://github.com/hahwul/dalfox.git", "git_go", "Powerful XSS scanner & parameter analyzer"),
    Tool("XSpear", "XSS Tools", "https://github.com/hahwul/XSpear.git", "git_generic", "Ruby XSS scanner", "run.rb|ruby"),
    Tool("XSStrike", "XSS Tools", "https://github.com/s0md3v/XSStrike.git", "git_python", "Advanced XSS detection suite", "xsstrike.py|python3"),

    # ── SQL Injection ───────────────────────────────────────────────────
    Tool("sqlmap", "SQL Injection", "https://github.com/sqlmapproject/sqlmap.git", "apt:sqlmap", "Automatic SQL injection & DB takeover"),
    Tool("NoSQLMap", "SQL Injection", "https://github.com/codingo/NoSQLMap.git", "git_python", "NoSQL / MongoDB injection tool", "nosqlmap.py|python3"),
    Tool("DSSS", "SQL Injection", "https://github.com/stamparm/DSSS.git", "git_python", "Damn Small SQLi Scanner", "dsss.py|python3"),

    # ── WiFi & Bluetooth ────────────────────────────────────────────────
    Tool("OneShot", "WiFi Tools", "https://github.com/kimocoder/OneShot.git", "git_python", "WPS pixie-dust / PMKID attack (no root DB)", "oneshot.py|python3"),
    Tool("wifipumpkin3", "WiFi Tools", "https://github.com/P0cL4bs/wifipumpkin3.git", "git_python", "Rogue AP / MITM framework", "wifipumpkin3|binary"),
    Tool("pixiewps", "WiFi Tools", "https://github.com/wiire-a/pixiewps.git", "apt:pixiewps", "Offline WPS pixie-dust brute force"),
    Tool("bluepot", "Bluetooth", "https://github.com/andrewmichaelsmith/bluepot.git", "git_generic", "Bluetooth honeypot"),
    Tool("btlejack", "Bluetooth", "https://github.com/virtualabs/btlejack.git", "pip:btlejack", "Bluetooth Low Energy sniff/hijack"),
    Tool("bluesnarfer", "Bluetooth", "https://github.com/Sante51/bluesnarfer.git", "git_generic", "Classic Bluetooth info extractor"),
    Tool("fluxion", "WiFi Tools", "https://github.com/FluxionNetwork/fluxion.git", "git_generic", "Evil-twin WPA handshake capture", "fluxion.sh|bash"),
    Tool("wifiphisher", "WiFi Tools", "https://github.com/wifiphisher/wifiphisher.git", "git_python", "Rogue AP phishing framework", "wifiphisher|binary"),
    Tool("wifite2", "WiFi Tools", "https://github.com/derv82/wifite2.git", "git_python", "Automated wireless auditor", "wifite.py|python3"),
    Tool("aircrack-ng", "WiFi Tools", "https://github.com/aircrack-ng/aircrack-ng.git", "apt:aircrack-ng", "WEP/WPA cracking suite"),
    Tool("bettercap", "WiFi Tools", "https://github.com/bettercap/bettercap.git", "apt:bettercap", "Swiss-army MITM & wireless framework"),
    Tool("hcxdumptool", "WiFi Tools", "https://github.com/ZerBea/hcxdumptool.git", "apt:hcxdumptool", "Capture PMKID / handshakes"),
    Tool("hcxtools", "WiFi Tools", "https://github.com/ZerBea/hcxtools.git", "apt:hcxtools", "Convert captures to hashcat format"),
    Tool("eaphammer", "WiFi Tools", "https://github.com/s0lst1c3/eaphammer.git", "git_python", "WPA2-Enterprise evil-twin attacks", "eaphammer|binary"),

    # ── Anonymity ───────────────────────────────────────────────────────
    Tool("kali-anonsurf", "Anonymity", "https://github.com/Und3rf10w/kali-anonsurf.git", "git_generic", "Route all traffic through Tor", "anonsurf|bash"),
    Tool("multitor", "Anonymity", "https://github.com/trimstray/multitor.git", "git_generic", "Many Tor instances with load balancing", "multitor.sh|bash"),

    # ── OSINT ───────────────────────────────────────────────────────────
    Tool("holehe", "OSINT", "https://github.com/megadose/holehe.git", "pip:holehe", "Check which sites an email is registered on"),
    Tool("maigret", "OSINT", "https://github.com/soxoj/maigret.git", "pip:maigret", "Username presence across 2500+ sites"),
    Tool("trufflehog", "OSINT", "https://github.com/trufflesecurity/trufflehog.git", "git_go", "Find leaked secrets in repos"),
    Tool("sherlock", "OSINT", "https://github.com/sherlock-project/sherlock.git", "apt:sherlock", "Hunt a username across social networks"),
    Tool("phoneinfoga", "OSINT", "https://github.com/sundowndev/phoneinfoga.git", "git_go", "Phone number OSINT"),
    Tool("GHunt", "OSINT", "https://github.com/mxrch/GHunt.git", "git_python", "Google account OSINT", "ghunt|binary"),
    Tool("shodan", "OSINT", "https://github.com/achillean/shodan-python.git", "pip:shodan", "Shodan CLI client"),
    Tool("censys", "OSINT", "https://github.com/censys/censys-python.git", "pip:censys", "Censys CLI client"),
    Tool("blackbird", "OSINT", "https://github.com/p1ngul1n0/blackbird.git", "git_python", "Fast username/email OSINT", "blackbird.py|python3"),

    # ── Exploitation & C2 ───────────────────────────────────────────────
    Tool("bulk_extractor", "Exploitation", "https://github.com/simsong/bulk_extractor.git", "apt:bulk-extractor", "Carve artifacts from disk/pcap images"),
    Tool("TheFatRat", "Exploitation", "https://github.com/screetsec/TheFatRat.git", "git_generic", "Backdoor & payload generator", "fatrat|binary"),
    Tool("msfpc", "Exploitation", "https://github.com/g0tmi1k/msfpc.git", "git_generic", "MSFvenom payload creator wizard", "msfpc|bash"),
    Tool("venom", "Exploitation", "https://github.com/r00t-3xp10it/venom.git", "git_generic", "Shellcode generator / payload builder", "venom.sh|bash"),
    Tool("metasploit", "C2 Frameworks", "https://github.com/rapid7/metasploit-framework.git", "apt:metasploit-framework", "The exploitation framework"),
    Tool("sliver", "C2 Frameworks", "https://github.com/bishopfox/sliver.git", "git_go", "Modern cross-platform C2"),
    Tool("havoc", "C2 Frameworks", "https://github.com/Havoc-Framework/Havoc.git", "git_generic", "Modern malleable C2 framework"),
    Tool("empire", "C2 Frameworks", "https://github.com/BC-SECURITY/Empire.git", "apt:powershell-empire", "PowerShell/Python post-exploit C2"),

    # ── Active Directory ────────────────────────────────────────────────
    Tool("netexec", "Active Directory", "https://github.com/Pennyw0rth/NetExec.git", "apt:netexec", "AD/network swiss-army knife (nxc)"),
    Tool("responder", "Active Directory", "https://github.com/lgandx/Responder.git", "apt:responder", "LLMNR/NBT-NS/MDNS poisoner"),
    Tool("impacket", "Active Directory", "https://github.com/fortra/impacket.git", "apt:python3-impacket", "Python network protocol toolkit"),
    Tool("bloodhound", "Active Directory", "https://github.com/specterops/bloodhound.git", "apt:bloodhound", "AD attack-path mapping (GUI)"),
    Tool("certipy", "Active Directory", "https://github.com/ly4k/Certipy.git", "pip:certipy-ad", "AD Certificate Services abuse"),
    Tool("BloodHound.py", "Active Directory", "https://github.com/Fox-IT/BloodHound.py.git", "git_python", "Python BloodHound ingestor", "bloodhound.py|python3"),
    Tool("mitm6", "Active Directory", "https://github.com/dirkjanm/mitm6.git", "pip:mitm6", "IPv6 DNS takeover for AD"),

    # ── Password Cracking & Wordlists ───────────────────────────────────
    Tool("hashcat", "Password Cracking", "https://github.com/hashcat/hashcat.git", "apt:hashcat", "World's fastest GPU hash cracker"),
    Tool("john", "Password Cracking", "https://github.com/openwall/john.git", "apt:john", "John the Ripper password cracker"),
    Tool("hydra", "Password Cracking", "https://github.com/vanhauser-thc/thc-hydra.git", "apt:hydra", "Network login brute forcer"),
    Tool("name-that-hash", "Password Cracking", "https://github.com/HashPals/Name-That-Hash.git", "pip:name-that-hash", "Identify a hash type"),
    Tool("cupp", "Wordlist", "https://github.com/Mebus/cupp.git", "git_python", "Profile-based wordlist generator", "cupp.py|python3"),
    Tool("SecLists", "Wordlist", "https://github.com/danielmiessler/SecLists.git", "git_generic", "The security tester's companion wordlists"),

    # ── Phishing ────────────────────────────────────────────────────────
    Tool("SET", "Phishing", "https://github.com/trustedsec/social-engineer-toolkit.git", "git_python", "Social-Engineer Toolkit", "se-toolkit|binary"),
    Tool("SocialFish", "Phishing", "https://github.com/UndeadSec/SocialFish.git", "git_python", "Phishing page framework", "SocialFish.py|python3"),
    Tool("evilginx2", "Phishing", "https://github.com/kgretzky/evilginx2.git", "git_go", "Man-in-the-middle reverse-proxy phishing"),
    Tool("gophish", "Phishing", "https://github.com/gophish/gophish.git", "git_go", "Open-source phishing campaign toolkit"),
    Tool("zphisher", "Phishing", "https://github.com/htr-tech/zphisher.git", "git_generic", "Automated phishing with tunnels"),

    # ── Post Exploitation ───────────────────────────────────────────────
    Tool("PEASS-ng", "Post Exploitation", "https://github.com/carlospolop/PEASS-ng.git", "git_generic", "linPEAS/winPEAS privilege-escalation audit", "linPEAS/linpeas.sh|bash"),
    Tool("pspy", "Post Exploitation", "https://github.com/DominicBreuker/pspy.git", "git_go", "Watch processes without root"),

    # ── RTL-SDR & Radio ─────────────────────────────────────────────────
    Tool("rtl-sdr", "RTL-SDR Radio", "https://github.com/osmocom/rtl-sdr.git", "apt:rtl-sdr", "Core RTL-SDR drivers & rtl_test/rtl_fm"),
    Tool("dump1090", "RTL-SDR Radio", "https://github.com/antirez/dump1090.git", "git_generic", "ADS-B aircraft decoder"),
    Tool("rtl_433", "RTL-SDR Radio", "https://github.com/merbanan/rtl_433.git", "apt:rtl-433", "Decode 433/315/868 MHz IoT & sensors"),
    Tool("gqrx", "RTL-SDR Radio", "https://github.com/gqrx-sdr/gqrx.git", "apt:gqrx", "GUI SDR spectrum receiver"),
    Tool("gnuradio", "RTL-SDR Radio", "https://github.com/gnuradio/gnuradio.git", "apt:gnuradio", "SDR signal-processing toolkit"),
    Tool("multimon-ng", "RTL-SDR Radio", "https://github.com/EliasOenal/multimon-ng.git", "apt:multimon-ng", "Decode POCSAG/AFSK/AX25 pager traffic"),
    Tool("kalibrate-rtl", "RTL-SDR Radio", "https://github.com/steve-m/kalibrate-rtl.git", "git_generic", "Measure RTL-SDR clock offset via GSM"),
    Tool("urh", "RTL-SDR Radio", "https://github.com/jopohl/urh.git", "pip:urh", "Universal Radio Hacker (reverse RF protocols)"),

    # ── System / Built-in ───────────────────────────────────────────────
    Tool("whois", "System", "", "apt:whois", "WHOIS registration lookup"),
    Tool("ping", "System", "", "apt:iputils-ping", "ICMP reachability probe"),

    # ── Additional / Labs ───────────────────────────────────────────────
    Tool("assetfinder", "Scanning & Recon", "https://github.com/tomnomnom/assetfinder.git", "git_go", "Find related domains/subdomains"),
    Tool("bombardier", "Web Scanning", "https://github.com/codesenberg/bombardier.git", "git_go", "HTTP(S) load/benchmark tool"),
    Tool("vulhub", "Lab & Training", "https://github.com/vulhub/vulhub.git", "git_generic", "Pre-built vulnerable Docker labs"),
]

ARSENAL = OrderedDict((t.name, t) for t in _TOOLS)

# Names that are first-class, intent-wired, curated tools (kept distinct from
# the bulk BlackArch catalog merged in below).
CURATED_TOOLS = frozenset(ARSENAL)


# ── Bulk BlackArch catalog ──────────────────────────────────────────────
# ~1700 extra tools imported from the BlackArch repo, filtered to ones that
# run on Kali/Debian (have an upstream git source; language-binding/library,
# config, no-source and wine/.NET-only packages were dropped) and de-duped
# against the curated set above. Stored as data (data/blackarch.json) rather
# than inline code to keep this module readable; each installs via upstream
# git clone and is browsable/launchable like any other arsenal entry.
import json as _json  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

BLACKARCH_FILE = _Path(__file__).with_name("data") / "blackarch.json"
BLACKARCH_TOOLS: List[str] = []


def _load_blackarch() -> None:
    try:
        rows = _json.loads(BLACKARCH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return  # catalog is optional; absence must never break the toolkit
    for r in rows:
        name = r.get("name")
        if not name or name in ARSENAL:
            continue
        ARSENAL[name] = Tool(
            name=name,
            category=r.get("category", "Misc"),
            url=r.get("url", ""),
            itype=r.get("itype", "git_generic"),
            description=r.get("desc", ""),
        )
        BLACKARCH_TOOLS.append(name)


_load_blackarch()


# Category -> ordered list of tool names (for the arsenal browser dialog).
# Built from the merged ARSENAL so BlackArch tools appear under their category.
def _build_categories():
    cats: "OrderedDict[str, List[str]]" = OrderedDict()
    for t in ARSENAL.values():
        cats.setdefault(t.category, []).append(t.name)
    return cats


CATEGORIES = _build_categories()


# ════════════════════════════════════════════════════════════════════════
#  ENTRYPOINTS / DEPS / ALIASES  (ported from Viking CLI)
# ════════════════════════════════════════════════════════════════════════
# name -> "script_relative_path|interpreter" (python3|bash|ruby|php|binary)
TOOL_ENTRYPOINTS = {t.name: t.entrypoint for t in _TOOLS if t.entrypoint}
TOOL_ENTRYPOINTS.update({
    "DSSS": "dsss.py|python3",
    "NoSQLMap": "nosqlmap.py|python3",
    "cupp": "cupp.py|python3",
})

# tool -> prerequisites: "apt:p1,p2|pip:p1,p2|go:pkg@latest"
TOOL_DEPS = {
    "theHarvester": "pip:dnspython,requests,censys,shodan",
    "recon-ng": "pip:dnspython,requests",
    "GHunt": "pip:requests,colorama,prompt_toolkit",
    "BloodHound.py": "pip:dnspython,impacket",
    "mitm6": "pip:impacket,dnspython",
    "eaphammer": "apt:hostapd,libssl-dev|pip:requests",
    "subfinder": "apt:libpcap-dev",
    "amass": "apt:libpcap-dev",
    "naabu": "apt:libpcap-dev",
    "wifiphisher": "apt:hostapd,dnsmasq",
    "bettercap": "apt:libpcap-dev,libnetfilter-queue-dev",
    "spiderfoot": "pip:dnspython,requests,pycryptodome",
    "arjun": "pip:requests,colorama",
    "censys": "pip:requests",
    "shodan": "pip:requests",
}

# canonical name -> actual binary on PATH (when they differ)
BIN_MAP = {
    "metasploit": "msfconsole",
    "RustScan": "rustscan",
    "name-that-hash": "nth",
    "theHarvester": "theHarvester",
    "SET": "setoolkit",
    "kali-anonsurf": "anonsurf",
    "PEASS-ng": "linpeas",
    "wifite2": "wifite",
}

# user-typed variant (lowercased) -> canonical arsenal name
NAME_ALIASES = {
    "webcheck": "WebCheck", "red_hawk": "RED_HAWK", "red-hawk": "RED_HAWK", "redhawk": "RED_HAWK",
    "theharvester": "theHarvester", "harvester": "theHarvester", "spiderfoot": "spiderfoot",
    "recon-ng": "recon-ng", "reconng": "recon-ng", "assetfinder": "assetfinder", "findomain": "findomain",
    "amass": "amass", "nmap": "nmap", "masscan": "masscan", "rustscan": "RustScan", "rust-scan": "RustScan",
    "httpx": "httpx", "subfinder": "subfinder", "naabu": "naabu", "dnsx": "dnsx",
    "dalfox": "dalfox", "xspear": "XSpear", "xsstrike": "XSStrike", "xss-strike": "XSStrike",
    "sqlmap": "sqlmap", "nosqlmap": "NoSQLMap", "dsss": "DSSS",
    "oneshot": "OneShot", "one-shot": "OneShot", "wifipumpkin3": "wifipumpkin3", "pixiewps": "pixiewps",
    "bluepot": "bluepot", "fluxion": "fluxion", "wifiphisher": "wifiphisher", "wifite2": "wifite2",
    "wifite": "wifite2", "aircrack": "aircrack-ng", "aircrack-ng": "aircrack-ng", "bettercap": "bettercap",
    "hcxdumptool": "hcxdumptool", "hcxtools": "hcxtools", "eaphammer": "eaphammer",
    "btlejack": "btlejack", "bluesnarfer": "bluesnarfer",
    "anonsurf": "kali-anonsurf", "kali-anonsurf": "kali-anonsurf", "multitor": "multitor",
    "holehe": "holehe", "maigret": "maigret", "trufflehog": "trufflehog", "truffle": "trufflehog",
    "sherlock": "sherlock", "phoneinfoga": "phoneinfoga", "ghunt": "GHunt", "shodan": "shodan",
    "censys": "censys", "blackbird": "blackbird",
    "cupp": "cupp", "seclists": "SecLists",
    "set": "SET", "setoolkit": "SET", "se-toolkit": "SET", "socialfish": "SocialFish",
    "evilginx2": "evilginx2", "evilginx": "evilginx2", "zphisher": "zphisher", "gophish": "gophish",
    "secretfinder": "SecretFinder", "secret-finder": "SecretFinder",
    "gobuster": "gobuster", "ffuf": "ffuf", "feroxbuster": "feroxbuster", "dirsearch": "dirsearch",
    "commix": "commix", "wpscan": "wpscan", "katana": "katana", "jaeles": "jaeles", "arjun": "arjun",
    "waybackurls": "waybackurls", "gau": "gau", "hakrawler": "hakrawler", "bombardier": "bombardier",
    "nikto": "nikto", "takeover": "takeover",
    "bulk_extractor": "bulk_extractor", "bulk-extractor": "bulk_extractor",
    "thefatrat": "TheFatRat", "fatrat": "TheFatRat", "msfpc": "msfpc", "venom": "venom",
    "vulhub": "vulhub",
    "netexec": "netexec", "nxc": "netexec", "cme": "netexec", "responder": "responder",
    "impacket": "impacket", "bloodhound": "bloodhound", "certipy": "certipy",
    "bloodhound.py": "BloodHound.py", "bloodhound-py": "BloodHound.py", "mitm6": "mitm6",
    "hashcat": "hashcat", "john": "john", "hydra": "hydra",
    "name-that-hash": "name-that-hash", "nth": "name-that-hash",
    "metasploit": "metasploit", "msf": "metasploit", "msfconsole": "metasploit",
    "sliver": "sliver", "havoc": "havoc", "empire": "empire", "nuclei": "nuclei",
    "peass": "PEASS-ng", "peass-ng": "PEASS-ng", "linpeas": "PEASS-ng", "pspy": "pspy",
    "rtl-sdr": "rtl-sdr", "rtlsdr": "rtl-sdr", "dump1090": "dump1090", "rtl_433": "rtl_433",
    "rtl433": "rtl_433", "gqrx": "gqrx", "gnuradio": "gnuradio", "multimon-ng": "multimon-ng",
    "multimon": "multimon-ng", "kalibrate-rtl": "kalibrate-rtl", "kal": "kalibrate-rtl", "urh": "urh",
}


def resolve_name(user_text: str) -> str:
    """Map a user-typed tool name to its canonical arsenal name."""
    low = user_text.strip().lower()
    if low in NAME_ALIASES:
        return NAME_ALIASES[low]
    stripped = re.sub(r"[ \-_.]", "", low)
    if stripped in NAME_ALIASES:
        return NAME_ALIASES[stripped]
    # Already canonical?
    for name in ARSENAL:
        if name.lower() == low:
            return name
    return user_text


# ════════════════════════════════════════════════════════════════════════
#  TARGET EXTRACTION
# ════════════════════════════════════════════════════════════════════════
_RX_IP = re.compile(r"\b(?:(?:[0-9]{1,3}\.){3}[0-9]{1,3})(?:/[0-9]{1,2})?\b")
_RX_URL = re.compile(r"https?://[^\s]+")
_RX_DOMAIN = re.compile(r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b")
_RX_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_RX_HASH = re.compile(r"\b[a-fA-F0-9]{16,}\b|\$[0-9a-zA-Z]+\$[^\s]+")


def extract_target(text: str, kind: str = "target"):
    """
    Pull the relevant token out of free text, matching Viking's extractor.
    kind: target (ip/url/domain) | url | domain | email | username | hash | none
    """
    if kind == "none":
        return None
    if kind == "email":
        m = _RX_EMAIL.search(text)
        return m.group(0) if m else None
    if kind == "hash":
        m = _RX_HASH.search(text)
        return m.group(0) if m else None
    if kind == "username":
        # last whitespace token that is not a keyword-ish word
        toks = text.split()
        return toks[-1] if toks else None
    if kind == "url":
        m = _RX_URL.search(text)
        if m:
            return m.group(0)
        m = _RX_DOMAIN.search(text)
        return ("http://" + m.group(0)) if m else None
    if kind == "domain":
        m = _RX_EMAIL.search(text)
        if m:  # strip domain off an email if present
            return m.group(0).split("@", 1)[1]
        m = _RX_DOMAIN.search(text)
        return m.group(0) if m else None
    # default "target": ip, then url, then domain
    for rx in (_RX_IP, _RX_URL, _RX_DOMAIN):
        m = rx.search(text)
        if m:
            return m.group(0)
    return None


# ════════════════════════════════════════════════════════════════════════
#  DEFAULT WORDLISTS
# ════════════════════════════════════════════════════════════════════════
WORDLIST_COMMON = "/usr/share/wordlists/dirb/common.txt"
WORDLIST_ROCKYOU = "/usr/share/wordlists/rockyou.txt"


# ════════════════════════════════════════════════════════════════════════
#  INTENT MAP  -  the heart of GUI tool orchestration.
#  Each intent lists candidate ToolActions; the GUI asks the operator which
#  one to run, shows the descriptions, then dispatches (installing on confirm).
# ════════════════════════════════════════════════════════════════════════
INTENTS: List[Intent] = [
    Intent(
        "port_scan", "Port / service scan",
        r"\b(scan|portscan|port scan|nmap|open ports?|services?)\b", "target",
        [
            ToolAction("nmap", "Service + version scan of open ports (reliable default)",
                       ["nmap", "-sV", "--open", "-T4", "{target}"], needs_root=True),
            ToolAction("RustScan", "Ultra-fast port sweep, then hands off to nmap",
                       ["rustscan", "-a", "{target}"]),
            ToolAction("naabu", "Fast SYN port finder (ProjectDiscovery)",
                       ["naabu", "-host", "{target}", "-silent"]),
            ToolAction("masscan", "Internet-scale async scanner (all ports, rate-limited)",
                       ["masscan", "{target}", "-p1-65535", "--rate=1000"], needs_root=True),
        ],
    ),
    Intent(
        "vuln_scan", "Vulnerability / CVE scan",
        r"\b(vulns?|vulnerab|cve|nuclei|nikto|weakness|check security)\b", "url",
        [
            ToolAction("nuclei", "Template-based CVE & misconfig scanner",
                       ["nuclei", "-u", "{target}", "-silent"]),
            ToolAction("nikto", "Classic web-server vulnerability scan",
                       ["nikto", "-h", "{target}"]),
        ],
    ),
    Intent(
        "dir_bruteforce", "Directory / content discovery",
        r"\b(dir(ectory)? ?scan|dir ?brute|content discovery|gobuster|ffuf|ferox|dirsearch|fuzz)\b", "url",
        [
            ToolAction("ffuf", "Fast web fuzzer (FUZZ keyword)",
                       ["ffuf", "-u", "{target}/FUZZ", "-w", WORDLIST_COMMON]),
            ToolAction("feroxbuster", "Recursive content discovery (Rust)",
                       ["feroxbuster", "-u", "{target}"]),
            ToolAction("gobuster", "Directory brute force",
                       ["gobuster", "dir", "-u", "{target}", "-w", WORDLIST_COMMON]),
            ToolAction("dirsearch", "Path brute forcer",
                       ["dirsearch", "-u", "{target}"]),
        ],
    ),
    Intent(
        "sqli", "SQL injection",
        r"\b(sqli|sql ?inject|sqlmap|database dump)\b", "url",
        [
            ToolAction("sqlmap", "Automated SQLi detection & exploitation (batch)",
                       ["sqlmap", "-u", "{target}", "--batch", "--level=1", "--risk=1"]),
        ],
    ),
    Intent(
        "xss", "Cross-site scripting",
        r"\b(xss|cross ?site|dalfox|xsstrike)\b", "url",
        [
            ToolAction("dalfox", "Fast XSS scanner & parameter analysis",
                       ["dalfox", "url", "{target}"]),
            ToolAction("XSStrike", "Advanced XSS detection suite",
                       ["XSStrike", "-u", "{target}"]),
        ],
    ),
    Intent(
        "cms_scan", "WordPress / CMS scan",
        r"\b(wpscan|wordpress|cms scan)\b", "url",
        [
            ToolAction("wpscan", "WordPress vuln/user/plugin enumeration",
                       ["wpscan", "--url", "{target}"]),
        ],
    ),
    Intent(
        "cmd_injection", "Command injection",
        r"\b(commix|command ?inject|os ?command)\b", "url",
        [
            ToolAction("commix", "Automated command-injection exploitation",
                       ["commix", "--url", "{target}"]),
        ],
    ),
    Intent(
        "web_crawl", "Web crawling / URL harvesting",
        r"\b(crawl|spider|katana|hakrawler|gau|wayback|endpoints?)\b", "domain",
        [
            ToolAction("katana", "Next-gen crawler/spider",
                       ["katana", "-u", "{target}"]),
            ToolAction("gau", "Fetch all known URLs for a domain",
                       ["gau", "{target}"]),
            ToolAction("waybackurls", "Historical URLs from the Wayback Machine",
                       ["waybackurls", "{target}"]),
            ToolAction("hakrawler", "Fast endpoint crawler",
                       ["hakrawler"], note="Pipe a URL in: echo {target} | hakrawler"),
        ],
    ),
    Intent(
        "subdomain", "Subdomain / domain recon",
        r"\b(subdomains?|subfinder|amass|enumerate domain|recon)\b", "domain",
        [
            ToolAction("subfinder", "Passive subdomain discovery",
                       ["subfinder", "-d", "{target}", "-silent"]),
            ToolAction("amass", "In-depth passive subdomain enumeration",
                       ["amass", "enum", "-passive", "-d", "{target}"]),
            ToolAction("theHarvester", "Emails, hosts & subdomains from OSINT sources",
                       ["theHarvester", "-d", "{target}", "-b", "all"]),
            ToolAction("dnsx", "DNS resolution / brute forcing",
                       ["dnsx", "-d", "{target}", "-silent"]),
        ],
    ),
    Intent(
        "osint_email", "Email OSINT",
        r"\b(holehe|email osint|account check|which sites.*email)\b", "email",
        [
            ToolAction("holehe", "Find sites where an email is registered",
                       ["holehe", "{target}"]),
        ],
    ),
    Intent(
        "osint_user", "Username OSINT",
        r"\b(sherlock|maigret|username|find user|social media hunt)\b", "username",
        [
            ToolAction("sherlock", "Hunt a username across social networks",
                       ["sherlock", "{target}"]),
            ToolAction("maigret", "Username presence across 2500+ sites",
                       ["maigret", "{target}"]),
            ToolAction("blackbird", "Fast username OSINT",
                       ["blackbird", "-u", "{target}"]),
        ],
    ),
    Intent(
        "hash_id", "Identify a hash",
        r"\b(what.{0,8}hash|identif\w*.{0,12}hash|name.?that.?hash|hash type)\b", "hash",
        [
            ToolAction("name-that-hash", "Identify the algorithm of a hash",
                       ["nth", "--text", "{target}"]),
        ],
    ),
    Intent(
        "password_crack", "Password / hash cracking",
        r"\b(hashcat|john the ripper|crack.{0,15}(hash|password)|brute.?force|hydra)\b", "none",
        [
            ToolAction("hashcat", "GPU hash cracking (interactive terminal)",
                       ["hashcat"], mode="interactive",
                       note="Example: hashcat -m 22000 hash.hc22000 " + WORDLIST_ROCKYOU),
            ToolAction("john", "John the Ripper (interactive terminal)",
                       ["john"], mode="interactive",
                       note="Example: john --wordlist=" + WORDLIST_ROCKYOU + " hashes.txt"),
            ToolAction("hydra", "Network login brute forcer (interactive terminal)",
                       ["hydra"], mode="interactive",
                       note="Example: hydra -l admin -P " + WORDLIST_ROCKYOU + " ssh://TARGET"),
        ],
    ),
    Intent(
        "wifi", "Wireless auditing",
        r"\b(wifi|wireless|wpa|wps|pmkid|handshake|evil ?twin|deauth)\b", "none",
        [
            ToolAction("wifite2", "Automated wireless auditor",
                       ["wifite"], mode="interactive", needs_root=True),
            ToolAction("OneShot", "WPS pixie-dust / PMKID attack",
                       ["OneShot"], mode="interactive", needs_root=True),
            ToolAction("bettercap", "MITM + wireless framework",
                       ["bettercap"], mode="interactive", needs_root=True),
            ToolAction("hcxdumptool", "Capture PMKID / handshakes",
                       ["hcxdumptool"], mode="interactive", needs_root=True),
            ToolAction("fluxion", "Evil-twin WPA handshake capture",
                       ["fluxion"], mode="interactive", needs_root=True),
        ],
    ),
    Intent(
        "active_directory", "Active Directory attacks",
        r"\b(active directory|\bad\b|netexec|nxc|responder|bloodhound|impacket|kerberoast|ntlm)\b", "none",
        [
            ToolAction("netexec", "AD/network swiss-army knife (interactive)",
                       ["netexec"], mode="interactive",
                       note="Example: nxc smb TARGET -u user -p pass"),
            ToolAction("responder", "LLMNR/NBT-NS poisoner",
                       ["responder", "-I", "eth0"], mode="interactive", needs_root=True),
            ToolAction("bloodhound", "AD attack-path mapping (GUI)",
                       ["bloodhound"], mode="interactive"),
            ToolAction("certipy", "AD Certificate Services abuse",
                       ["certipy"], mode="interactive"),
        ],
    ),
    Intent(
        "exploit", "Exploitation / C2 / payloads",
        r"\b(metasploit|msfconsole|meterpreter|payload|sliver|havoc|c2|reverse shell|msfpc)\b", "none",
        [
            ToolAction("metasploit", "The exploitation framework (interactive)",
                       ["msfconsole"], mode="interactive"),
            ToolAction("msfpc", "MSFvenom payload creator wizard",
                       ["msfpc"], mode="interactive"),
            ToolAction("sliver", "Modern cross-platform C2",
                       ["sliver"], mode="interactive"),
            ToolAction("havoc", "Malleable C2 framework",
                       ["havoc"], mode="interactive"),
        ],
    ),
    Intent(
        "phishing", "Phishing / social engineering",
        r"\b(phish|setoolkit|social ?engineer|evilginx|gophish|zphisher)\b", "none",
        [
            ToolAction("SET", "Social-Engineer Toolkit (interactive)",
                       ["setoolkit"], mode="interactive", needs_root=True),
            ToolAction("evilginx2", "Reverse-proxy MITM phishing",
                       ["evilginx2"], mode="interactive"),
            ToolAction("gophish", "Phishing campaign toolkit (web UI)",
                       ["gophish"], mode="interactive"),
            ToolAction("zphisher", "Automated phishing with tunnels",
                       ["zphisher"], mode="interactive"),
        ],
    ),
    Intent(
        "anonymity", "Anonymity / Tor routing",
        r"\b(anonsurf|anonymi|route.*tor|hide.*ip|torify)\b", "none",
        [
            ToolAction("kali-anonsurf", "Route all traffic through Tor",
                       ["anonsurf", "start"], mode="interactive", needs_root=True),
        ],
    ),
    Intent(
        "post_exploit", "Post-exploitation / privesc",
        r"\b(linpeas|privesc|priv ?esc|privilege escalation|pspy|enumerate (box|host))\b", "none",
        [
            ToolAction("PEASS-ng", "linPEAS privilege-escalation audit",
                       ["linpeas"], mode="interactive"),
            ToolAction("pspy", "Watch processes without root",
                       ["pspy"], mode="interactive"),
        ],
    ),
    Intent(
        "adsb", "ADS-B aircraft tracking",
        r"\b(adsb|ads-b|dump1090|flight|aircraft|plane track)\b", "none",
        [
            ToolAction("dump1090", "Live ADS-B aircraft radar (needs RTL-SDR dongle)",
                       ["dump1090", "--interactive", "--net"], mode="interactive"),
        ],
    ),
    Intent(
        "sdr_sensors", "433/315 MHz sensor decode",
        r"\b(rtl.?433|sensor|433 ?mhz|iot radio|weather station)\b", "none",
        [
            ToolAction("rtl_433", "Decode IoT/weather/TPMS sensors (needs RTL-SDR)",
                       ["rtl_433"], mode="interactive"),
        ],
    ),
    Intent(
        "sdr_spectrum", "SDR spectrum / radio",
        r"\b(gqrx|sdr|spectrum|software defined radio|gnuradio|urh|radio scan|multimon)\b", "none",
        [
            ToolAction("gqrx", "GUI SDR spectrum receiver (needs display)",
                       ["gqrx"], mode="interactive"),
            ToolAction("urh", "Universal Radio Hacker - reverse RF protocols",
                       ["urh"], mode="interactive"),
            ToolAction("multimon-ng", "Decode POCSAG/AFSK/AX25 pager traffic",
                       ["multimon-ng"], mode="interactive",
                       note="Example: rtl_fm -f 152.04M -s 22050 | multimon-ng -t raw -a POCSAG512 -f alpha -"),
        ],
    ),
    Intent(
        "whois", "WHOIS / registration lookup",
        r"\b(whois|registrar|domain owner|registration)\b", "domain",
        [
            ToolAction("whois", "WHOIS registration lookup (built-in)",
                       ["whois", "{target}"]),
        ],
    ),
    Intent(
        "ping", "Host reachability",
        r"\b(ping|is.*up|reachable|alive)\b", "target",
        [
            ToolAction("ping", "ICMP reachability probe (built-in)",
                       ["ping", "-c", "4", "{target}"]),
        ],
    ),
]


# Broad intents are checked last so specific web/osint intents win first.
# (e.g. "dir scan" -> dir_bruteforce, not the generic "scan" -> port_scan).
_BROAD_PRIORITY = {"port_scan": 90, "ping": 95, "subdomain": 60, "web_crawl": 55}
for _intent in INTENTS:
    _intent.priority = _BROAD_PRIORITY.get(_intent.key, 50)

# Stable, priority-sorted order used by detect_intent.
_SORTED_INTENTS = sorted(INTENTS, key=lambda i: i.priority)


def detect_intent(text: str) -> Optional[Intent]:
    """Return the best-matching intent (specific before broad), or None for chat."""
    for intent in _SORTED_INTENTS:
        if intent.matches(text):
            return intent
    return None


def find_tool(name: str) -> Optional[Tool]:
    """Look up a Tool by canonical name (after alias resolution)."""
    canonical = resolve_name(name)
    return ARSENAL.get(canonical)
