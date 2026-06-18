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
$ git clone https://github.com/zathras777/shelly-fw.git
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
Scanning subnet 192.168.0.0/24 using 50 workers...
Found 21 device(s)

19 device(s) need updated...

Updating MiniPMG3 device(s)...
...
```

## Notes

- an http server will be created to serve the downloaded firmware files using an IP address that is automaticlly identified and port 8007.
- version matching is used to get the latest version of suitable firmware, but updates are not done automatically
- stable versions will not be changed to beta

## Acknowledgements

This gist was very helpful. https://gist.github.com/Greysayan/a90e0c5f7a96901190d33397ed6551ff
