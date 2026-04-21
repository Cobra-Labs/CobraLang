# 🐍 Cobra Programming Language

**Cobra** ist eine moderne Systemprogrammier-Sprache, die die Eleganz von **Python** mit der Performance von **C** vereint. Direkt zu Maschinencode kompiliert, ohne Garbage Collector – perfekt für die Kernel-Entwicklung.

---

## ✨ Key Features

* **Pythonic Syntax:** Voller Support für Indentation (Einrückung).
* **Flexible Blocks:** Nutze entweder `:` + Indent oder `{` + `}`.
* **Static Typing:** C-Typen wie `i32`, `u8`, `ptr` und `structs`.
* **Bare-Metal:** Läuft freestanding (ohne Betriebssystem).
* **Direct Memory:** Volle Kontrolle über Pointer und Speicheradressen.

---

## 🛠 Syntax-Vorschau (.co)

# Beispiel: VGA Treiber in Cobra
struct VGAChar:
    character: u8
    color: u8

def kmain(magic: u32, addr: *u32) -> i32:
    # Direkter Zugriff auf VGA Buffer
    video_mem: *VGAChar = cast(*VGAChar, 0xB8000)
    
    if magic == 0x2BADB002:
        video_mem[0].character = 0x43 # 'C'
        video_mem[0].color = 0x0F     # Weiß auf Schwarz
    
    return 0

---

## 🏗 Architektur

Cobra nutzt das **LLVM-Backend**, um hochoptimierten Code zu erzeugen.
1. **Frontend:** Parser in Python (übersetzt .co Dateien).
2. **IR-Gen:** Erzeugung von LLVM Intermediate Representation.
3. **Compilation:** Finales Binary via LLVM (ELF/Bin).

---

## 🛠️ Contact & Support

If you have questions about **Cobra**, our **CPU architectures**, or the **Open Fixture Language**, feel free to reach out!

* 📧 **Email:** [support-cobralabs@proton.me](mailto:support-cobralabs@proton.me)
* 🌐 **GitHub Org:** [github.com/CobraLabs](#) (Link anpassen)
* ☕ **Support our work:** [Support us on Ko-fi](https://ko-fi.com)

---

## 🗺 Roadmap

- [x] Sprach-Design
- [ ] Prototyp Compiler (Python)
- [ ] LLVM-Integration
- [ ] Bootfähiger Kernel Demo
- [ ] **Self-Hosting:** Cobra schreibt seinen eigenen Compiler

---

**Cobra: Code like a snake, strike like a machine.** ⚡