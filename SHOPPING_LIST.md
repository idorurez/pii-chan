# Mira Shopping List

**Date:** 2025-03-06  
**Purpose:** Phase 1 hardware for Pi validation

---

## Order Tonight ✓

### Core Hardware

| Item | Purpose | Est. Price | Link |
|------|---------|------------|------|
| ☐ **Raspberry Pi 5 8GB** | Main compute | $80 | [Adafruit](https://www.adafruit.com/product/5813) / [Amazon](https://amazon.com) |
| ☐ **Pi 5 27W USB-C Power Supply** | Dev power | $12 | [Adafruit](https://www.adafruit.com/product/5814) |
| ☐ **SD Card 128GB A2** | Fast storage | $15 | Samsung EVO Select or SanDisk Extreme |
| ☐ **Pi 5 Active Cooler** | Prevent throttling | $8 | [Adafruit](https://www.adafruit.com/product/5815) |

### Display

| Item | Purpose | Est. Price | Link |
|------|---------|------------|------|
| ☐ **Waveshare 7" Touchscreen** | Config + Mira face | $55 | [Amazon](https://amazon.com/dp/B07L6WT77H) / [Waveshare](https://waveshare.com) |

*1024x600, HDMI input, USB touch, IPS panel*

### Audio

| Item | Purpose | Est. Price | Link |
|------|---------|------------|------|
| ☐ **USB Microphone** | Voice input | $20 | ReSpeaker USB Mic Array or similar |
| ☐ **USB/3.5mm Speaker** | Voice output | $15 | Any small powered speaker |

### CAN Hardware

| Item | Purpose | Est. Price | Link |
|------|---------|------------|------|
| ☐ **Waveshare 2-CH CAN HAT** | CAN bus read/write | $25 | [Amazon](https://amazon.com/dp/B07VMB1ZKH) |
| ☐ **WiCAN Pro OBD-II** | WiFi CAN sniffing | $55 | [MeatPi](https://meatpi.com/products/wican) |

---

## Phase 1 Total: ~$285

---

## Car Installation (Later)

| Item | Purpose | Est. Price |
|------|---------|------------|
| ☐ 12V→5V 5A Buck Converter | Car power | $12 |
| ☐ OBD-II Y-Splitter | Share OBD port | $10 |
| ☐ Display Mount | Dashboard mount | $15 |
| ☐ USB cables, zip ties | Clean install | $10 |

**Car install total:** ~$47

---

## Optional Upgrades (Future)

| Item | Purpose | Est. Price |
|------|---------|------------|
| ☐ Waveshare SIM7600 4G HAT | Dedicated cellular | $70 |
| ☐ T-Mobile prepaid data SIM | Monthly data | $10/mo |
| ☐ HyperPixel 4.0 | Smaller 4" display | $55 |
| ☐ MAX98357A I2S Amp + Speaker | Higher quality audio | $15 |

---

## Quick Links

- **Pi 5:** https://www.adafruit.com/product/5813
- **Waveshare 7" Display:** https://www.waveshare.com/7inch-hdmi-lcd-c.htm
- **2-CH CAN HAT:** https://www.waveshare.com/2-ch-can-hat.htm
- **WiCAN:** https://meatpi.com/products/wican

---

## Vendor Notes

| Vendor | Ships From | Speed |
|--------|------------|-------|
| Adafruit | NYC | 2-3 days |
| Amazon | Various | 1-2 days (Prime) |
| Waveshare | China/US warehouse | Varies |
| MeatPi (WiCAN) | Check stock | 3-5 days |

**Recommendation:** Amazon/Adafruit for speed. Check WiCAN stock first.

---

## After Purchase

1. Flash Raspberry Pi OS (64-bit) to SD card
2. Boot and enable SSH
3. Install Node.js 22
4. Install OpenClaw
5. Test connection to AWS gateway

See `PRODUCT.md` → Phase 1 for validation steps.
