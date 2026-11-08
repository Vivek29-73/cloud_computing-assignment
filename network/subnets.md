# Subnet allocation for 10.20.0.0/16

Rule: usable hosts = 2^(32 - prefix) - 2. Allocate largest first, starting at 10.20.0.0, each subnet right after the previous one, smallest prefix that fits.

## Working

| Subnet | Hosts needed | Smallest fit | Prefix | Block size |
|---|---|---|---|---|
| app | 1,000 | 2^10 - 2 = 1,022 (2^9 - 2 = 510 is too small) | /22 | 1,024 |
| public | 250 | 2^8 - 2 = 254 (2^7 - 2 = 126 is too small) | /24 | 256 |
| data | 100 | 2^7 - 2 = 126 (2^6 - 2 = 62 is too small) | /25 | 128 |
| management | 20 | 2^5 - 2 = 30 (2^4 - 2 = 14 is too small) | /27 | 32 |

Placement: app starts at 10.20.0.0 and covers 1,024 addresses, so it ends at 10.20.3.255. public starts at 10.20.4.0 and ends at 10.20.4.255. data starts at 10.20.5.0 and ends at 10.20.5.127. management starts at 10.20.5.128 and ends at 10.20.5.159.

## Table

| Subnet | Network address | Prefix | Usable host range | Broadcast address | Usable hosts |
|---|---|---|---|---|---|
| app | 10.20.0.0 | /22 | 10.20.0.1 - 10.20.3.254 | 10.20.3.255 | 1,022 |
| public | 10.20.4.0 | /24 | 10.20.4.1 - 10.20.4.254 | 10.20.4.255 | 254 |
| data | 10.20.5.0 | /25 | 10.20.5.1 - 10.20.5.126 | 10.20.5.127 | 126 |
| management | 10.20.5.128 | /27 | 10.20.5.129 - 10.20.5.158 | 10.20.5.159 | 30 |
