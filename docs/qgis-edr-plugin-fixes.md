# Ispravke QGIS EDR dodatka (edr_plugin 1.1.0, QGIS 4)

Dodatak „Environmental Data Retrieval” (`edr_plugin` 1.1.0) na QGIS 4 ne radi sa pygeoapi 0.24.0
bez izmena. Tri male izmene to rešavaju. Sve tri su greške u dodatku, ne u pygeoapi-ju.

## Gde se nalazi dodatak

| Sistem | Folder |
|---|---|
| Linux | `~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/edr_plugin/` |
| Windows | `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\edr_plugin\` |
| macOS | `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/edr_plugin/` |

Pre izmene sačuvati kopiju svakog fajla (npr. `cp file.py file.py.orig`). Posle izmene restartovati QGIS.
Ažuriranje ili ponovna instalacija dodatka briše izmene, pa ih možda treba ponovo uraditi; prvo proveriti
da li novija verzija već rešava problem.

Brojevi linija ispod važe za verziju 1.1.0 i mogu se pomeriti u drugim verzijama; bolje je tražiti navedeni kod.

---

## Ispravka 1: dijalog se ruši pri izboru kolekcije

**Greška:**

```
Populating data query attributes failed ... addItem(...): argument 1 has unexpected type 'dict'
```

**Uzrok:** pygeoapi upisuje oznake parametara kao jezičke mape, npr. `{"en": "Air temperature"}`, što
CoverageJSON dozvoljava. Dijalog ovaj rečnik direktno prosleđuje padajućoj listi, koja očekuje tekst.

**Fajl:** `gui/__init__.py`, oko linije 437, u petlji koja popunjava `self.parameters_cbo`.

**Izmena:** posle linije `observed_property_label = observed_property["label"]` dodati dve linije koje uzimaju
englesku oznaku (ili prvu dostupnu) kada je oznaka rečnik:

```diff
                 else:
                     observed_property = parameter_data["observedProperty"]
                     observed_property_label = observed_property["label"]
+                if isinstance(observed_property_label, dict):
+                    observed_property_label = observed_property_label.get("en", next(iter(observed_property_label.values())))
                 parameter_description = parameter_data.get("description", observed_property_label)
                 self.parameters_cbo.addItem(parameter_description, parameter)
```

`if` mora biti na istom uvlačenju kao `parameter_description = …`, tj. van bloka `else:`.

---

## Ispravka 2: rezultati sa vremenskom osom se ne učitavaju

**Greška:**

```
type object 'Type' has no attribute 'DateTime'
```

**Uzrok:** dodatak koristi Qt 5 naziv tipa `DateTime`. U Qt 6, na kome je napravljen QGIS 4, ta vrednost
se zove `QDateTime`.

**Fajl:** `coveragejson/coverage.py`, oko linije 334.

**Izmena:** zameniti `QMetaType.Type.DateTime` sa `QMetaType.Type.QDateTime`:

```diff
         if self.has_t:
-            layer.dataProvider().addAttributes([QgsField(self.FIELD_NAME_TIME, QMetaType.Type.DateTime)])
+            layer.dataProvider().addAttributes([QgsField(self.FIELD_NAME_TIME, QMetaType.Type.QDateTime)])
```

Ako se ista greška pojavi i na drugom mestu, potražiti `QMetaType.Type.DateTime` u celom dodatku i
zameniti svako pojavljivanje.

---

## Ispravka 3: rezultati sa stanica (locations, area) se ne učitavaju

**Greška:**

```
Missing `referencing` element in coverage collection.
```

**Uzrok:** pygeoapi stavlja podatke o koordinatnom sistemu (`referencing`) u `domain` svakog coverage-a,
što CoverageJSON dozvoljava. Dodatak ih traži samo na vrhu `CoverageCollection`.

**Fajl:** `coveragejson/coverage_json_reader.py`, oko linije 53, u metodi koja vraća element referencing.

**Izmena:** pre bacanja greške potražiti `referencing` u domain-u coverage-a:

```diff
         if self.is_collection:
             if "referencing" not in self.coverage_json:
+                for coverage in self.coverage_json.get("coverages", []):
+                    if "referencing" in coverage.get("domain", {}):
+                        return coverage["domain"]["referencing"]
                 raise ValueError("Missing `referencing` element in coverage collection.")
 
             return self.coverage_json["referencing"]
```

---

## Provera

Posle restarta QGIS-a otvoriti dodatak, dodati server (npr. `http://localhost:8090/ogc`) i probati:

- `inca-grid` → **Position** i **Cube**: sloj tačaka sa jednom tačkom po satu, ili jedan raster po satu
  koji se animira u Temporal Controller-u;
- `stations-edr` → **Locations** i **Area**: slojevi tačaka sa vremenskim serijama.

Ako se sva četiri učitaju, ispravke rade.

## Vraćanje izmena

Kopirati `.orig` fajlove preko izmenjenih ili ponovo instalirati dodatak iz menadžera dodataka.
