# Integrácia SSE eZóna pre Home Assistant

*English: a Home Assistant integration for SSE eZóna (ezona.sse.sk), the customer portal of Stredoslovenská energetika, providing tariff prices and billing data. User documentation is in Slovak; developer documentation is in English in [DEVELOPMENT.md](DEVELOPMENT.md).*

> **Vo vývoji** — integráciu už môžete pridať a uloží vaše prihlasovacie údaje, ale z portálu zatiaľ nič nenačítava.

Integrácia pre zákaznícky portál Stredoslovenskej energetiky [SSE eZóna](https://ezona.sse.sk). Je určená pre zákazníkov SSE odoberajúcich elektrinu v ktorejkoľvek distribučnej oblasti (SSD, ZSD alebo VSD).

## Funkcie

Plánované údaje pre každé odberné miesto:

- **Aktuálna cena VT/NT** (EUR/kWh vrátane DPH), pri jednotarifnej sadzbe jedna cena JT
- **Saldo**: suma na úhradu alebo preplatok
- **Zálohová platba**: výška a frekvencia
- **Sadzba dodávky** (napr. `DD5`)
- **Posledná faktúra**: celková suma a dátum splatnosti

Ceny môžu slúžiť na výpočet nákladov v [integrácii SSD IMS](https://github.com/baracudaz/ssd-ims) (pozri baracudaz/ssd-ims#33) alebo kdekoľvek inde v Home Assistante.

## Obmedzenia

- Podporované sú len účty s prihlásením používateľským menom (e-mailom) a heslom. Prihlásenie cez Google, Facebook alebo Apple a účty s jednorazovým kódom (SMS/QR) podporované nie sú.
- Koncové ceny, ktoré eZóna zobrazuje, nemusia zahŕňať adresnú energopomoc na rok 2026. Podrobnosti nájdete v issues.
- Portál povoľuje na jeden účet len jedno prihlásenie naraz, takže prihlásenie z Home Assistantu vás môže odhlásiť z eZóny v prehliadači.

## Prečo táto integrácia

Pre SSE už existujú dve komunitné integrácie (pozri [Podobné projekty](#podobné-projekty)). Obe sa sústreďujú na spotrebu z eZóny. Táto integrácia dopĺňa to, čo vie len dodávateľ:

- **Skutočne fakturovaná cena**: koncová cena VT/NT (alebo JT), ktorú SSE fakturuje, vrátane adresnej energopomoci — nie zmluvná cena silovej elektriny ani cena bez energopomoci.
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
