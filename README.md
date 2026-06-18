# shelly-fw

Small script to update shelly devices that live on a different subnet and have no direct internet access.

## Installation

This script requires Python 3.11+ and pipx.

Install pipx first if needed:

```sh
brew install pipx [macos]
sudo apt install pipx [ubuntu]
sudo apk add pipx [alpine]
```

Then clone this repository and run the installation script:

```
$ git clone https://github.com/
$ cd shelly-fw
$ ./install.sh
```

If `shelly-fw` is not found after installation, open a new shell or run:

```sh
$ pipx ensurepath
```

## Usage

```
$ shelly-fw 192.168.0.0/24
Scanning subnet: 10.0.74.0/24
192.168.0.15 gen=3 model=S3PM-001PCEU16 app=MiniPMG3 version=1.7.1 id=shellypmminig3-xxx
...
```

## Acknowledgements

This gist was very helpful. https://gist.github.com/Greysayan/a90e0c5f7a96901190d33397ed6551ff
