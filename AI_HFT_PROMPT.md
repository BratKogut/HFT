# Prompt dla AI: Budowa Systemu HFT (High-Frequency Trading) - Blueprint 2026

## 📜 TWOJA ROLA I CEL

Jesteś światowej klasy inżynierem i architektem systemów HFT z ponad 20-letnim doświadczeniem w budowaniu ultra-nisk latencyjnych systemów dla czołowych firm tradingowych. Twoim zadaniem jest stworzenie **kompletnego, szczegółowego i realistycznego blueprintu** dla nowoczesnego systemu HFT, który miałby być zbudowany w 2026 roku.

**Cel:** Wygeneruj dokument, który posłuży jako **materiał edukacyjny** dla studentów, inżynierów i badaczy, aby zrozumieli złożoność, koszty i architekturę profesjonalnych systemów HFT.

---

## ⚠️ **BARDZO WAŻNY DISCLAIMER** ⚠️

**Zacznij swoją odpowiedź od poniższego ostrzeżenia. Musi być ono jasne i widoczne.**

"**OSTRZEŻENIE:** Ten blueprint jest przeznaczony **wyłącznie do celów edukacyjnych i teoretycznych**. Budowa prawdziwego systemu HFT jest ekstremalnie kosztowna, ryzykowna i złożona. Wymaga kapitału w wysokości **$1M-5M**, zespołu **5-10+ wyspecjalizowanych inżynierów** i **wieloletniego doświadczenia**. **NIE JEST TO PROJEKT** dla indywidualnych deweloperów, małych zespołów ani nikogo bez odpowiedniego zaplecza finansowego i technologicznego. Handel na rynkach finansowych wiąże się z wysokim ryzykiem utraty kapitału."

---

## 🎯 GŁÓWNE ZAŁOŻENIA SYSTEMU

Twoja propozycja musi spełniać następujące kryteria:

1.  **Docelowe Latency:** Poniżej **1 mikrosekundy (end-to-end)**, od otrzymania danych rynkowych do wysłania zlecenia.
2.  **Rok Projektowy:** Architektura i technologie muszą być aktualne na **2026 rok**.
3.  **Architektura:** System musi być oparty na **trójwarstwowej architekturze hybrydowej (FPGA + C++ + Python)**.

---

## 🏗️ ZADANIE 1: SZCZEGÓŁOWA ARCHITEKTURA SYSTEMU

Opisz szczegółowo każdą z trzech warstw architektury. Dla każdej warstwy podaj:
- **Cel:** Jaka jest jej główna rola w systemie?
- **Kluczowe Komponenty:** Jakie moduły się na nią składają?
- **Technologie:** Jakie języki programowania i narzędzia są używane?
- **Oczekiwane Latency:** Jakie są czasy przetwarzania dla każdego komponentu?

### Warstwa 1: FPGA (Hardware - "The Speed Layer")
- **Cel:** Wykonywanie prostych, powtarzalnych zadań z nanosekundową precyzją, omijając system operacyjny.
- **Komponenty do opisania:**
    1.  **Market Data Ingestion:** Odbiór danych z giełdy.
    2.  **FIX/ITCH Parser:** Dekodowanie protokołów giełdowych.
    3.  **Pre-Trade Risk Checks:** Ultra-szybkie, podstawowe kontrole ryzyka (np. "fat-finger checks").
    4.  **Order Gateway:** Kodowanie i wysyłanie zleceń.
- **Technologie:** Verilog/VHDL.

### Warstwa 2: C++ (Software - "The Brain Layer")
- **Cel:** Implementacja złożonej logiki strategii, zarządzanie stanem i podejmowanie decyzji.
- **Komponenty do opisania:**
    1.  **Strategy Engine:** Główny silnik, gdzie działają strategie HFT (np. market making, arbitraż statystyczny).
    2.  **Complex Event Processing (CEP):** Identyfikacja złożonych wzorców w danych rynkowych.
    3.  **Position Management:** Śledzenie aktualnych pozycji, PnL i ryzyka.
- **Technologie:** C++20/23 (z użyciem coroutines, concepts), lock-free data structures, kernel bypass (DPDK, Solarflare Onload).

### Warstwa 3: Python (Software - "The Research Layer")
- **Cel:** Badania, analiza danych, trenowanie modeli i monitoring.
- **Komponenty do opisania:**
    1.  **Research & Analytics:** Tworzenie i testowanie nowych strategii na danych historycznych.
    2.  **Model Training:** Trenowanie modeli AI/ML, które mogą być wykorzystane przez silnik C++.
    3.  **Monitoring & Dashboard:** Wizualizacja metryk systemowych w czasie rzeczywistym.
- **Technologie:** Python 3.11+, Jupyter, Pandas, NumPy, scikit-learn, TensorFlow/PyTorch, Grafana.

---

## ⚙️ ZADANIE 2: INFRASTRUKTURA I STOS TECHNOLOGICZNY

Opisz szczegółowo wymaganą infrastrukturę i technologie wspierające.

1.  **Co-location:** Wyjaśnij, dlaczego jest to kluczowe i podaj przykłady data center (np. Equinix NY4, LD4).
2.  **Hardware:**
    - **Serwery:** Specyfikacja (wysoki zegar CPU, np. Intel Xeon E-series).
    - **Karty Sieciowe (NICs):** Solarflare, Mellanox.
    - **FPGA:** Xilinx Alveo, Intel Stratix.
    - **Switche:** Arista, Cisco (ultra-low latency).
    - **Synchronizacja Czasu:** Wyjaśnij rolę PTP i sprzętu jak White Rabbit switch.
3.  **Sieć:**
    - Opisz rolę **kernel bypass** (DPDK, Onload).
    - Standardy sieciowe (10/25/100 Gbps Ethernet).
4.  **Stos Oprogramowania:**
    - **System Operacyjny:** Linux z patchem real-time.
    - **Kompilatory:** GCC/Clang z flagami optymalizacyjnymi.
    - **System Budowania:** CMake/Bazel.
    - **CI/CD:** Jenkins/GitLab CI z uwzględnieniem testów hardware.

---

## ✍️ ZADANIE 3: PRZYKŁADY KODU

Dostarcz **krótkie, ilustracyjne przykłady kodu** dla kluczowych komponentów, aby zwizualizować ich działanie.

1.  **Verilog (FPGA):** Uproszczony fragment parsera ITCH.
2.  **C++ (Strategy Engine):** Szkielet prostej strategii market making (np. pseudokod lub uproszczony C++).
3.  **Python (Research):** Krótki skrypt w Pandas do analizy order book imbalance na danych historycznych.

---

## 💰 ZADANIE 4: ANALIZA KOSZTÓW I ZESPOŁU

Stwórz realistyczne zestawienie kosztów i wymagań zespołowych.

1.  **Koszty w Pierwszym Roku:** Podziel na kategorie (Co-location, Hardware, Dane rynkowe, Pensje, Zgodność z regulacjami, Kapitał operacyjny) i podaj szacunkowe widełki.
2.  **Wymagany Zespół:** Wymień kluczowe role (np. C++ Low-Latency Developer, FPGA Engineer, Quantitative Analyst, Infrastructure Engineer, Compliance Officer) i opisz ich główne obowiązki.

---

## 📅 ZADANIE 5: PLAN IMPLEMENTACJI

Zaproponuj realistyczny, fazowy plan wdrożenia projektu w czasie (9-18 miesięcy).

-   **Faza 1: Discovery & Architecture (2-3 miesiące)**
-   **Faza 2: Core Development (4-6 miesięcy)**
-   **Faza 3: Testing & Optimization (2-4 miesiące)**
-   **Faza 4: Deployment & Live Trading (1-2 miesiące)**

---

## 🏁 ZADANIE 6: WNIOSKI I REKOMENDACJE

Zakończ swój blueprint podsumowaniem i rekomendacją, która odzwierciedla ducha oryginalnego dokumentu.

**Podkreśl, że dla 99.9% deweloperów i małych firm, budowa takiego systemu jest nierealistyczna i nierentowna.**

**Zarekomenduj alternatywną ścieżkę:**
- Skupienie się na **systemach średniej częstotliwości** (gdzie Python jest wystarczający).
- Koncentracja na znalezieniu przewagi w **strategii (mózg)**, a nie w **szybkości (pieniądze)**.
- Wykorzystanie wiedzy z tego blueprintu do ulepszenia istniejących, prostszych systemów tradingowych.

Twoja ostateczna odpowiedź powinna być zorganizowana, technicznie precyzyjna i wierna założeniom, przedstawiając realistyczny, ale edukacyjny obraz świata HFT.