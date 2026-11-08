# Integrácia SSE eZóna pre Home Assistant

*English: a Home Assistant integration for SSE eZóna (ezona.sse.sk), the customer portal of Stredoslovenská energetika, providing tariff prices and billing data. User documentation is in Slovak; developer documentation is in English in [DEVELOPMENT.md](DEVELOPMENT.md).*

> **Vo vývoji**

Integrácia pre zákaznícky portál Stredoslovenskej energetiky [SSE eZóna](https://ezona.sse.sk). Je určená pre zákazníkov SSE odoberajúcich elektrinu v ktorejkoľvek distribučnej oblasti (SSD, ZSD alebo VSD).

## Funkcie

Každé vybrané odberné miesto elektriny je v Home Assistante samostatné zariadenie s týmito snímačmi:

- **Koncová cena VT a NT** (EUR/kWh vrátane DPH), pri jednotarifnej sadzbe **Koncová cena JT**. Atribút `valid_from` hovorí, odkedy cena platí; kým integrácia nezaznamená prvú zmenu ceny, je prázdny.
- **Mesačná platba**: pevná mesačná platba za odberné miesto vrátane DPH
- **Na úhradu**: aktuálna dlžná suma
- **Výška zálohy**: atribút `frequency` hovorí, ako často sa platí
- **Sadzba** (napr. `DD5`)
- **Posledná faktúra**: celková suma s DPH, nedoplatok/preplatok (preplatok je záporný) a dátum splatnosti
- **Fakturovaná spotreba VT a NT** (kWh), pri jednotarifnej sadzbe **Fakturovaná spotreba JT**: spotreba za posledné zúčtovacie obdobie; atribúty `period_from` a `period_to` udávajú obdobie. Slúži na porovnanie s odpočtami elektromera, napríklad zo [SSD IMS](https://github.com/baracudaz/ssd-ims). Nejde o meranie, preto sa nezobrazuje v paneli **Energie**.

Údaje sa načítavajú raz denne.

### Ako sa počíta koncová cena

eZóna priamo neuvádza aktuálnu koncovú cenu. Integrácia ju skladá z dvoch častí:

- **zmluvná cena silovej elektriny** z detailu odberného miesta — je vždy aktuálna,
- **regulovaná časť** (distribúcia, straty, systémové poplatky, odvod do Národného jadrového fondu) z koncových cien na poslednej vyúčtovacej faktúre.

Zmena ceny silovej elektriny sa tak prejaví nasledujúci deň; zmena regulovanej časti až s ďalšou faktúrou.

### Adresná energopomoc

Ceny v eZóne nezahŕňajú adresnú energopomoc. Ak na ňu odberné miesto má nárok, integrácia ju od ceny silovej elektriny odpočíta, takže koncová cena zodpovedá skutočne fakturovanej cene. V roku 2026 je energopomoc 31,24 €/MWh bez DPH pre všetky sadzby (zákon č. 260/2025 Z. z.).

- Nárok sa predvolene preberá z údaja „Nárok na adresnú energopomoc“ v eZóne. Po kliknutí na **Konfigurovať** pri vašom účte ho môžete pre každé odberné miesto nastaviť ručne (*Automaticky*, *Uplatniť*, *Neuplatniť*).
- Výšku energopomoci eZóna neuvádza, integrácia ju má zabudovanú pre každý rok. Ak sa zmení skôr, ako vyjde nová verzia integrácie, zadajte ju v časti **Rozšírené** toho istého dialógu.
- Pre rok, ktorého výšku integrácia nepozná, sa energopomoc neodpočíta a v logu sa objaví upozornenie.
- Atribúty cenových snímačov ukazujú, čo sa odpočítalo: `energy_aid` (€/MWh bez DPH), `price_without_aid` (cena bez energopomoci), `energy_aid_eligible` (nárok podľa eZóny) a `energy_aid_classified_on` (dátum zaradenia).

Ceny môžu slúžiť na výpočet nákladov v [integrácii SSD IMS](https://github.com/baracudaz/ssd-ims) (pozri baracudaz/ssd-ims#33) alebo kdekoľvek inde v Home Assistante.

## Obmedzenia

- Podporované sú len účty s prihlásením používateľským menom (e-mailom) a heslom. Prihlásenie cez Google, Facebook alebo Apple a účty s jednorazovým kódom (SMS/QR) podporované nie sú.
- Portál povoľuje na jeden účet len jedno prihlásenie naraz, takže prihlásenie z Home Assistantu vás môže odhlásiť z eZóny v prehliadači.

## Prečo táto integrácia

Pre SSE už existujú dve komunitné integrácie (pozri [Podobné projekty](#podobné-projekty)). Obe sa sústreďujú na spotrebu z eZóny. Táto integrácia dopĺňa to, čo vie len dodávateľ:

- **Koncová cena, nie len cena silovej elektriny**: koncová cena VT/NT (alebo JT) vrátane distribúcie, regulovaných poplatkov a DPH, po odpočítaní adresnej energopomoci, ak na ňu máte nárok.
- **Ceny ako zdroj pre výpočet nákladov**: cenové senzory sú určené na výpočet hodinových nákladov v [integrácii SSD IMS](https://github.com/baracudaz/ssd-ims) alebo kdekoľvek inde v Home Assistante; Home Assistant si uchováva ich históriu, takže zmena ceny platí od hodiny, keď nastala.
- **Všetky odberné miesta účtu** v jednom nastavení.
- **Spotrebu neduplikuje**: priebeh spotreby pochádza od distribútora (pre oblasť SSD integrácia SSD IMS). Funguje teda aj vtedy, keď eZóna profilové údaje nesprístupňuje, a nezávisí od toho, kto je váš dodávateľ.
- **Plánované rozšírenia**: [samoodpočty z údajov SSD IMS](https://github.com/baracudaz/sse-ezona/issues/14), [odhad vyúčtovania](https://github.com/baracudaz/sse-ezona/issues/15), [kontrola faktúr](https://github.com/baracudaz/sse-ezona/issues/16) a [plánované odstávky](https://github.com/baracudaz/sse-ezona/issues/17).

## Podobné projekty

| Projekt | Čo poskytuje |
|---------|--------------|
| [stullko/hacs-sse-energy](https://github.com/stullko/hacs-sse-energy) (`sse_energy`) | Spotreba VT/NT a náklady z 15-minútového profilu eZóny pre panel Energie, ceny VT/NT (zmluvná cena silovej elektriny × DPH, distribúcia odhadnutá z ročných nákladov), saldo, zálohy, posledné vyúčtovanie a údaje zo zmluvy. Jedno odberné miesto na jedno nastavenie. |
| [Isiala/ha-sse-ezona](https://github.com/Isiala/ha-sse-ezona) (`sse_ezona`) | Hodinové štatistiky spotreby z exportu 15-minútového profilu eZóny pre panel Energie. Bez cien a fakturačných údajov. Jedno odberné miesto na jedno nastavenie. |

Majte na pamäti:

- **Spotreba v oboch projektoch závisí od profilových údajov v eZóne**, ktoré SSE nesprístupňuje pre všetky odberné miesta. Ak v eZóne v časti **Spotreba** nemáte k odbernému miestu profilové (15-minútové) údaje, spotrebu z eZóny nezískate — použite údaje od distribútora.
- Táto integrácia a Isiala/ha-sse-ezona používajú rovnakú doménu `sse_ezona`, preto ich nemožno mať nainštalované súčasne.

## Inštalácia

### Spôsob 1: Marketplace (odporúčané, Home Assistant 2026.11 a novší)

Od verzie 2026.11 je HACS súčasťou Home Assistantu ako **Marketplace**. Integrácia zatiaľ nie je v jeho predvolenom katalógu, preto ju pridajte cez odkaz:

1. Otvorte **Nastavenia** → **Marketplace** (pri prvom otvorení potvrďte upozornenie)
2. Zvoľte **Pridať z odkazu** a zadajte `https://github.com/baracudaz/sse-ezona` (vyžaduje pripojenie k GitHubu)
3. Zvoľte **Inštalovať**, skontrolujte verziu a znova zvoľte **Inštalovať**
4. Hneď sa otvorí nastavenie integrácie; ak Home Assistant potrebuje najprv reštart, ponúkne ho v časti **Opravy**

Ak ste integráciu nainštalovali cez HACS pred verziou 2026.11, nemusíte nič robiť: Marketplace prevezme správu od HACS a aktualizácie nájdete v časti **Nastavenia** → **Aktualizácie**.

### Spôsob 2: HACS (Home Assistant starší ako 2026.11)

1. Otvorte HACS, v ponuke (⋮) zvoľte „Custom repositories“
2. Pridajte `https://github.com/baracudaz/sse-ezona` s kategóriou „Integration“
3. Vyhľadajte „Stredoslovenská energetika (SSE eZóna)“ a zvoľte „Download“
4. Reštartujte Home Assistant

### Spôsob 3: Ručná inštalácia

1. Stiahnite tento repozitár
2. Skopírujte priečinok `custom_components/sse_ezona` do priečinka `config/custom_components/` vo vašom Home Assistante
3. Reštartujte Home Assistant
4. Pridajte integráciu (pozri [Nastavenie](#nastavenie))

## Nastavenie

1. Otvorte **Nastavenia** → **Zariadenia a služby**
2. Zvoľte **Pridať integráciu**
3. Vyhľadajte „Stredoslovenská energetika (SSE eZóna)“
4. Zadajte používateľské meno (e-mail) a heslo k účtu SSE eZóna
5. Vyberte odberné miesta, ktoré chcete pridať (ak má účet len jedno, tento krok sa preskočí)

Výber odberných miest a nárok na energopomoc môžete neskôr zmeniť tlačidlom **Konfigurovať** pri položke vášho účtu v integrácii.

Ak eZóna neskôr heslo odmietne (napríklad po jeho zmene), Home Assistant vás vyzve na opätovné prihlásenie.

## Riešenie problémov

### Podrobné protokolovanie

Pri riešení problémov zapnite podrobné protokolovanie:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.sse_ezona: debug
```

## Autori

Spravuje [baracudaz](https://github.com/baracudaz).

## Licencia

Projekt je licencovaný pod AGPLv3 — podrobnosti v súbore [LICENSE](LICENSE).

## Prispievanie

Vývoj, testy a postup pri prispievaní sú popísané (v angličtine) v [DEVELOPMENT.md](DEVELOPMENT.md).
