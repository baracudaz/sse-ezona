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
