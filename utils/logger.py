import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

def log_info(msg):
    print(f"{Fore.CYAN}[INFO] {msg}{Style.RESET_ALL}")

def log_success(msg):
    print(f"{Fore.GREEN}[SUCCESS] {msg}{Style.RESET_ALL}")

def log_warning(msg):
    print(f"{Fore.YELLOW}[WARNING] {msg}{Style.RESET_ALL}")

def log_error(msg):
    print(f"{Fore.RED}[ERROR] {msg}{Style.RESET_ALL}")