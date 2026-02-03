import requests
import time
import random
from datetime import datetime, timedelta
from collections import defaultdict

class ProxyManager:
    def __init__(self, provider, config):
        self.provider = provider
        self.config = config
        self.proxies = []
        self.blacklist = set()
        self.sticky_sessions = defaultdict(list)
        self.last_check = datetime.now()
        self.load_proxies()

    def load_proxies(self):
        if self.provider == 'bright_data':
            self.proxies = self.load_proxies_from_bright_data()
        elif self.provider == 'ip_royal':
            self.proxies = self.load_proxies_from_ip_royal()
        elif self.provider == 'generic_list':
            self.proxies = self.load_proxies_from_file()
        else:
            raise ValueError("Unsupported provider")

    def load_proxies_from_bright_data(self):
        # Implement Bright Data API call
        return ["http://proxy1:port", "http://proxy2:port"]

    def load_proxies_from_ip_royal(self):
        # Implement IP Royal API call
        return ["http://proxy1:port", "http://proxy2:port"]

    def load_proxies_from_file(self):
        with open(self.config['proxy_file'], 'r') as file:
            return [line.strip() for line in file.readlines()]

    def get_proxy(self):
        if not self.proxies:
            self.load_proxies()
        proxy = random.choice(self.proxies)
        self.sticky_sessions[proxy].append(datetime.now())
        return proxy

    def mark_failed(self, proxy):
        self.blacklist.add(proxy)
        self.proxies.remove(proxy)
        print(f"Proxy {proxy} marked as failed")

    def mark_success(self, proxy):
        self.proxies.remove(proxy)
        self.proxies.insert(0, proxy)
        print(f"Proxy {proxy} marked as successful")

    def check_proxies(self):
        if datetime.now() - self.last_check > timedelta(hours=1):
            for proxy in self.proxies:
                try:
                    response = requests.get("http://example.com", proxies={"http": proxy, "https": proxy}, timeout=5)
                    if response.status_code == 200:
                        self.mark_success(proxy)
                except requests.RequestException:
                    self.mark_failed(proxy)
            self.last_check = datetime.now()

    def get_playwright_context_options(self, proxy):
        return {
            "proxy": proxy,
            "ignore_https_errors": True
        }

# Example usage
config = {
    "proxy_file": "proxies.txt"
}
proxy_manager = ProxyManager('generic_list', config)
proxy = proxy_manager.get_proxy()
print(proxy)