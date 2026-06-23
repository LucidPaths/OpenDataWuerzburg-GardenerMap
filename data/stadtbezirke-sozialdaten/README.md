# Würzburg Stadtbezirke – konsolidierte Sozial- & Demografiedaten

Konsolidierung der metrik-fragmentierten Open-Data-Datensätze der Stadt Würzburg auf
**Stadtbezirks-Ebene (13 Einheiten)** in **eine breite Tabelle** plus Datenkatalog.

**Quelle / Lizenz:** `Quelle: Stadt Würzburg – opendata.wuerzburg.de` (dl-de/by-2-0)
**API:** Opendatasoft Explore API v2.1 – `https://opendata.wuerzburg.de/api/explore/v2.1`
**Datenabruf:** 2026-06-23 · **Jahresabdeckung:** 2011–2025 (je Kennzahl unterschiedlich)

## Dateien
| Datei | Inhalt |
|---|---|
| `Wuerzburg_Stadtbezirke_Sozialdaten.xlsx` | Deliverable mit 5 Tabellenblättern (s. u.) |
| `build.py` | Reproduzierbare Pipeline: lädt die Datensätze per API und baut das `.xlsx` |
| `long_all.csv` | Tidy-Langtabelle aller Kennzahlen (Stadtbezirk × Jahr × Kennzahl × Wert) |

Reproduzieren: `pip install pandas openpyxl && python3 build.py`
(`FETCH=0 python3 build.py` nutzt nur lokal gecachte CSVs unter `data/`.)

## Tabellenblätter
1. **Konsolidiert** – breite Tabelle, 13 Stadtbezirke + Gesamtstadt, je Kennzahl das
   *aktuellste valide Jahr* (Jahr in `[…]` in der Spaltenüberschrift).
2. **Zeitreihe** – vollständige Historie als Langtabelle (alle Jahre, alle Kennzahlen).
3. **Datenkatalog** – je Kennzahl: Quell-`dataset_id`, Definition, Jahre, nativ vs.
   abgeleitet, Lücken/Hinweise.
4. **Coverage** – Matrix Kennzahl × Stadtbezirk (vorhanden ✓ / fehlt –) im jeweils
   aktuellsten Jahr.
5. **Quellen_Methodik** – Lizenz, Join-Logik, Definitionen, Datenqualitäts-Notizen.

## Geografische Abgrenzung
Stadt Würzburg, **13 Stadtbezirke**. Die historische 25-Stadtteil-Gliederung wurde 1990
abgeschafft; amtliche Statistik existiert nur auf Stadtbezirks-Ebene. Dürrbachtal wird als
**eine** Einheit geführt (interne Teilung Dürrbachau/Ober-/Unterdürrbach ignoriert).
Join-Schlüssel = Stadtbezirk. Namensvarianten wurden normalisiert (Umlaut ↔ ae/oe/ue),
da die Demografie-Datensätze ASCII-gefaltete Namen (`Grombuehl`, `Duerrbachtal`) nutzen,
Geo-/Sozialmonitoring-Datensätze hingegen Umlaute (`Grombühl`).

## Gelieferte Kennzahlen (je Stadtbezirk)
- **Ausländer**: Anzahl (+ weiblich) und **Ausländeranteil %** (abgeleitet).
- **Deutsche mit Migrationshintergrund**: Anzahl (+ weiblich, Durchschnittsalter) und
  **Anteil %** (abgeleitet).
- **Durchschnittsalter** (gesamt, Ausländer, Migrationshintergrund) und **Medianalter**.
- **Kinderanteil** – Bänder klar definiert: **u3** (0–2), **u6** (0–2+3–5),
  **u18** (0–17), jeweils Anzahl + Anteil % (abgeleitet aus den Altersgruppen).
- **Kinderbetreuungsplätze**: Plätze <3 J. und 3–6 J. (absolut), 2015–2025.
- Kontext: Haushalte (Anzahl, Durchschnittsgröße, mit Kindern <18), Wohnberechtigte,
  Jugend-/Alten-/Abhängigkeitsquotient, Greying-Index, Geburten/Sterbefälle/Zu-/Wegzüge.

### Abgeleitete Raten – Formel
`Anteil % = Kennzahl ÷ Einwohner(Hauptwohnsitz) × 100`, jeweils **gleicher Stadtbezirk
und gleiches Jahr**. Bevölkerungsbegriff: melderechtlich registrierte Einwohner am Ort
der Hauptwohnung (Mehrfachwohnsitze einfach gezählt).

## Datenqualität – dokumentierte Befunde (nicht kaschiert)
- **Kinderbetreuungsplätze sind vorhanden** – entgegen der ursprünglichen Annahme. Sie
  liegen jedoch **nicht** unter `stadtbezirke_*`, sondern im Datensatz
  `sozialmonitoring-betreuungsplaetze-fur-kinder` (auf Stadtbezirks-Ebene, mit eigener
  Gesamtstadt-Zeile „Würzburg"). Im Katalog entsprechend als „anderer Datensatz" markiert.
- **Korrupte Altersgruppen-Zeilen:** `stadtbezirke_hauptwohnsitz_altersgruppen` enthält
  2126 Artefaktzeilen ohne Stadtbezirk/Jahr (Label `Column 1`…`Column 15`) – verworfen.
  Saubere Altersdaten reichen nur bis **2023** → Kinderanteile enden 2023, übrige
  Kennzahlen bis 2024/2025.
- **Unvollständiges Jahr 2025:** Bei mehreren Zähl-Datensätzen (`hauptwohnsitz`,
  `auslaender`, `wohnberechtigte`, …) ist 2025 ein Platzhalter (Summe ≈ 0,1 % des
  Vorjahres) oder eine exakte 2024-Dublette (`auslaender_weiblich`). Solche Jahre wurden
  je Kennzahl automatisch erkannt und entfernt; das aktuellste *valide* Jahr steht in der
  Spaltenüberschrift.
- **Irreführendes `_2019`-Suffix:** Datensätze mit Suffix `…_2019` enthalten dennoch
  Zeitreihen bis 2025.
- **Gesamtstadt-Zeile:** Zählwerte = Summe der 13 Bezirke; Durchschnittsalter =
  bevölkerungsgewichtetes Mittel; Median/Quotienten sind nicht aggregierbar (leer);
  Betreuungsplätze aus der portaleigenen „Würzburg"-Zeile.
- **Keine Versorgungsquote für Betreuung** abgeleitet, da Platzzahlen (bis 2025) und
  Altersbänder (bis 2023) jahresverschieden sind – als Lücke dokumentiert.

## Nicht flachgejoint (im Portal vorhanden, separat)
Detail-Breakdowns wie `*_altersgruppen`, `*_staatsangehoerigkeit_2019`,
`haushalte_personen_2019`, `hauptwohnsitz_altersgruppen_weiblich` – im Katalog erwähnt,
aber nicht in die Breittabelle aufgenommen (mehrdimensional).
