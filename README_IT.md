# FLIR Temperature Exporter 1.0.1

[English](README.md) | **Italiano** | [中文](README_中文.md)

Strumento autonomo per estrarre matrici di temperatura in gradi Celsius dalle immagini JPEG radiometriche FLIR, singolarmente o in batch. Utilizza Python, NumPy, Pillow ed ExifTool e può essere eseguito indipendentemente dal progetto di tesi.

Il programma legge i dati termici a 16 bit incorporati nel file e i relativi parametri di misura, applica le correzioni ambientali e l'inversione di Planck, quindi esporta una matrice bidimensionale di temperature. La matrice mantiene la griglia termica originale, senza ritaglio, rotazione, ribaltamento o ridimensionamento.

È possibile scaricare il [pacchetto v1.0.1 pronto all'uso](https://github.com/AlexFei2001/FLIR-Temperature-Extraction-Package/raw/refs/heads/main/dist/FLIR_Temperature_Exporter_v1.0.1_2026-11-10.zip), oppure l'intero repository tramite **Code → Download ZIP** su GitHub. Prima dell'esecuzione, estrarre tutta la cartella dell'archivio.

## 1. Installazione delle dipendenze Python

Utilizzare Python 3.10–3.14. Aprire un terminale nella cartella estratta ed eseguire:

```text
python -m pip install -r requirements.txt
```

Sono necessarie soltanto NumPy e Pillow. Il file delle dipendenze richiede Pillow dalla versione 12.2 fino alla versione precedente alla 13, per mantenere la modalità di decodifica a 16 bit utilizzata nei test e il supporto a Python 3.10. `requirements-tested.txt` riporta le versioni esatte di NumPy e Pillow dell'ambiente verificato.

Conda è facoltativo. Per creare un ambiente dedicato:

```text
conda create -n flir_export python=3.11 -y
conda activate flir_export
python -m pip install -r requirements.txt
```

## 2. Installazione e configurazione di ExifTool

Scaricare ExifTool seguendo le [istruzioni ufficiali](https://exiftool.sourceforge.net/install.html).

Su Windows si consiglia la versione eseguibile: dopo l'estrazione, rinominare `exiftool(-k).exe` in `exiftool.exe` e mantenere accanto ad esso la cartella associata `exiftool_files`. La distribuzione completa in Perl richiede invece un interprete Perl e la propria cartella `lib`.

Copiare `config.example.json` in `config.json`. In PowerShell:

```powershell
Copy-Item config.example.json config.json
```

Su Linux/macOS è possibile utilizzare `cp config.example.json config.json`.

Modificare il percorso di ExifTool in base al proprio computer. Esempio:

```json
{
  "exiftool_command": ["C:/Tools/ExifTool/exiftool.exe"],
  "raw_byte_order": "swap16",
  "measurement_overrides": {}
}
```

Nei percorsi JSON utilizzare preferibilmente `/`. Un percorso con spazi deve rimanere un'unica stringa, senza aggiungere ulteriori virgolette all'interno della stringa. I percorsi relativi dei file sono risolti rispetto alla cartella del file di configurazione. Se ExifTool è disponibile nel PATH, è sufficiente `["exiftool"]`.

Per la versione Perl, un esempio di comando è `["perl", "vendor/exiftool/exiftool"]`. In questo caso occorre conservare anche la cartella `lib` della distribuzione.

### Verifica dell'ordine dei byte

La scelta deve essere esplicita:

- `native`: utilizza i valori uint16 così come vengono decodificati da Pillow.
- `swap16`: scambia i due byte di ogni valore a 16 bit.

**Il valore `swap16` nell'esempio è stato utilizzato per quattro specifici file FLIR T1020; non è un'impostazione universale per tutti i file FLIR.** Per una nuova fotocamera o un nuovo formato, verificare la scelta confrontando le temperature negli stessi pixel e con gli stessi parametri nel software FLIR. Un ordine errato può causare un errore oppure produrre temperature finite ma scorrette; l'aspetto visivo non è sufficiente per validarlo. Il programma non sceglie automaticamente l'ordine dei byte.

Verificare le dipendenze e la lettura della configurazione:

```text
python extract_flir.py --check --config config.json
```

Questo controllo conferma che gli strumenti sono disponibili, ma non convalida l'ordine dei byte né l'accuratezza delle temperature.

## 3. Estrazione di una singola immagine o di una cartella

Singola immagine:

```text
python extract_flir.py --input "D:/FLIR photos/IR_0016.jpg" --output "D:/FLIR exports" --config config.json --csv
```

Intera cartella:

```text
python extract_flir.py --input "D:/FLIR photos" --output "D:/FLIR exports" --config config.json --csv
```

Aggiungere `--recursive` per includere le sottocartelle. Dopo `--input` si possono indicare più file o cartelle, separati da spazi e racchiudendo ciascun percorso tra virgolette quando necessario. L'opzione `--csv` è facoltativa: senza di essa viene comunque salvata la matrice NPY.

Se la cartella contiene fotografie ordinarie o file privi dei metadati necessari, questi vengono registrati come errori senza generare temperature inventate. L'elaborazione degli altri file prosegue; controllare infine `summary.csv`.

È disponibile anche una modalità interattiva nel terminale:

```text
python extract_flir.py --interactive
```

Questa modalità legge `config.json` dalla cartella dello strumento, se presente, e richiede un percorso di input, una cartella di output e la scelta di esportare anche i CSV. Su Windows si può avviare `run_windows.cmd` con un doppio clic. Con Conda è preferibile eseguire `python` dal terminale dopo avere attivato l'ambiente corretto.

Per tutte le opzioni: `python extract_flir.py --help`.

## 4. Struttura e significato dei risultati

Ogni esecuzione crea una sottocartella con data/ora UTC e identificativo casuale, senza sovrascrivere immagini originali o risultati precedenti:

```text
FLIR exports/
└── <data_ora_UTC_identificativo>/
    ├── manifest.json
    ├── summary.csv
    ├── summary.json
    └── 0001_IR_0016/
        ├── temperature.npy
        ├── temperature.csv       # con l'opzione --csv
        ├── radiometry.json
        ├── preview_gray.png
        └── source_display.png
```

| File | Contenuto e utilizzo |
|---|---|
| `temperature.npy` | Matrice completa delle temperature in °C, float64, forma `(altezza, larghezza)`. È il formato preferibile per il calcolo numerico. |
| `temperature.csv` | La stessa matrice, senza intestazioni o indici, separatore `,`, punto decimale `.`, 17 cifre significative per preservare i valori nella rilettura. |
| `radiometry.json` | Parametri originali ed effettivi, ordine dei byte, unità, dimensioni, informazioni di decodifica e hash dei dati. |
| `preview_gray.png` | Immagine di visualizzazione a 8 bit sulla griglia termica, con intervallo dal 1° al 99° percentile. I valori dei pixel non sono temperature in °C. |
| `source_display.png` | Visualizzazione contenuta nel JPEG, eventualmente con scala, testi o fusione con il visibile; non è una matrice di temperatura. |
| `summary.csv/json` | Esito per ciascun file, cartella di output, intervallo di temperatura e messaggi di errore. |
| `manifest.json` | Configurazione del batch, versioni software, informazioni di provenienza e hash degli output. |

La limitazione dell'intervallo della preview riguarda soltanto la visualizzazione; i dati numerici mantengono tutte le temperature. Le sottocartelle sono numerate per distinguere file con lo stesso nome provenienti da cartelle diverse.

I CSV possono essere importati in Excel indicando la virgola come separatore dei campi e il punto come separatore decimale, indipendentemente dalle impostazioni locali italiane. I file CSV possono essere più grandi dei corrispondenti NPY.

## 5. Lettura della matrice in Python

```python
import numpy as np
T = np.load("temperature.npy", allow_pickle=False)
print(T.shape)           # (altezza, larghezza)
print(T[20, 10])         # temperatura in °C al pixel x=10, y=20
print(T.min(), T.max(), T.mean())
```

Le coordinate partono da zero e l'indicizzazione è `T[y, x]`.

Esempio con lo script incluso:

```text
python read_temperature_example.py "D:/FLIR exports/<run>/0001_IR_0016/temperature.npy" --x 10 --y 20
```

La griglia termica può avere dimensioni o coordinate diverse dalla visualizzazione JPEG, soprattutto in presenza di bordi, scale o immagini fuse. Non assumere una corrispondenza diretta senza verificarla.

È inoltre possibile importare `extract_frame` da `flir_reader.py`: restituisce `(temperature_c, source_display_rgb, metadata)` e richiede esplicitamente ordine dei byte e comando ExifTool come lista di argomenti.

## 6. Parametri di misura e limiti del modello

Per impostazione predefinita sono utilizzati i parametri originali del file: emissività, distanza, temperatura apparente riflessa, temperatura atmosferica, umidità, temperatura e trasmissione della finestra IR, costanti di Planck e coefficienti atmosferici. Se mancano i metadati di calibrazione necessari, il programma rifiuta la conversione anziché introdurre valori generici.

Il modello mantiene le espressioni numeriche dell'adattatore già utilizzato nel progetto di tesi. Assume due semipercorsi atmosferici di uguale lunghezza, con la finestra IR tra essi. Percorsi ottici particolari, altri modelli di fotocamera, firmware o metadati incompleti richiedono verifiche specifiche.

Per impostazioni di misura note si possono indicare valori espliciti nell'oggetto `measurement_overrides`. I valori originali e quelli utilizzati vengono entrambi registrati. Sono ammessi soltanto:

| Campo | Significato e unità |
|---|---|
| `Emissivity` | Emissività, maggiore di 0 e non superiore a 1 |
| `ObjectDistance` | Distanza in metri, non negativa |
| `RelativeHumidity` | Frazione tra 0 e 1; 60% corrisponde a `0.6` |
| `ReflectedApparentTemperature` | Temperatura apparente riflessa, °C |
| `AtmosphericTemperature` | Temperatura atmosferica, °C |
| `IRWindowTemperature` | Temperatura della finestra IR, °C |
| `IRWindowTransmission` | Trasmissione della finestra, maggiore di 0 e non superiore a 1 |

Le costanti di calibrazione non possono essere sostituite tramite questa configurazione. I parametri di misura devono descrivere le condizioni reali di acquisizione, non essere modificati per ottenere un risultato visivamente preferibile.

**Le temperature esportate sono stime corrette mediante i metadati, non misure la cui accuratezza assoluta sia stata calibrata indipendentemente.** Il campo `absolute_numeric_validation_complete` rimane `false`. Per nuove sorgenti, confrontare più pixel con il software FLIR usando le stesse coordinate e impostazioni. Il numero di decimali memorizzati in float64 non rappresenta l'accuratezza del sensore.

Il pacchetto supporta JPEG radiometrici con dati compatibili, non tutti i formati FLIR. Non estrae temperature da fotografie ordinarie, screenshot, JPEG privati dei metadati, file BMT o immagini DJI.

## 7. Risoluzione dei problemi

- **ExifTool non trovato:** verificare percorso, PATH e cartella associata `exiftool_files` o `lib`.
- **RawThermalImage assente:** utilizzare il JPEG radiometrico originale; una fotografia visibile o un'esportazione della sola palette non contiene la matrice richiesta.
- **Metadati di calibrazione mancanti:** utilizzare un file originale completo o una matrice di temperatura esportata dal software del produttore.
- **Nonpositive corrected signal / invalid Planck inversion:** verificare ordine dei byte e parametri di misura; non considerare valida una conversione fallita.
- **Raw image must be exact-size 16-bit:** verificare il formato del file e la versione di Pillow specificata nelle dipendenze.
- **Solo alcuni file falliscono:** consultare `summary.csv`; gli altri continuano a essere elaborati.
- **Dimensioni diverse tra JPEG e matrice:** verificare la griglia termica originale e la presenza di bordi o fusione nell'immagine di visualizzazione.

Codici di uscita: `0` se tutti i file sono stati elaborati e le sorgenti sono rimaste invariate; `2` in presenza di errori per singolo file o modifiche alle sorgenti; `1` per errori di configurazione o avvio degli strumenti.

## 8. File del pacchetto e test

- `extract_flir.py`: interfaccia da terminale ed esportazione batch.
- `flir_reader.py`: decodifica dei dati FLIR e conversione in temperatura.
- `config.example.json`: modello di configurazione portabile.
- `read_temperature_example.py`: esempio di lettura della matrice e di un pixel.
- `run_windows.cmd`: avvio della modalità interattiva su Windows.
- `tests/test_exporter.py`: test sintetici senza fotografie reali o installazione di ExifTool.
- `VALIDATION.md` e `validation_report.json`: ambito delle verifiche effettuate.
- `SOURCE_PROVENANCE.json`: provenienza del codice numerico e informazioni di versione.

Esecuzione facoltativa dei test:

```text
python -m pip install -r requirements-test.txt
python -m pytest tests -q
```

La versione è stata verificata su Windows con Python 3.10.20, NumPy 2.2.6, Pillow 12.2.0 ed ExifTool 13.61: 17 test autonomi e 20 test di regressione dell'adattatore originale sono passati. Le matrici di quattro file reali FLIR T1020 sono identiche ai risultati archiviati, e la rilettura dei CSV conserva gli stessi valori. La coerenza numerica non sostituisce una calibrazione termometrica indipendente. Altri sistemi operativi e tipi di fotocamera non sono stati verificati su file reali in questa versione.

Il pacchetto distribuito contiene codice e documentazione; fotografie private, matrici del dataset, eseguibili esterni e configurazioni specifiche del computer non sono inclusi.

## Licenza e riferimenti

Il codice è distribuito secondo la [licenza MIT del repository](LICENSE). Gli strumenti e le librerie di terze parti mantengono le rispettive licenze e vengono installati separatamente.

- [Installazione ufficiale di ExifTool](https://exiftool.sourceforge.net/install.html)
- [Tag FLIR, dati termici e ordine dei byte](https://exiftool.sourceforge.net/TagNames/FLIR.html)
- [Versioni Python supportate da Pillow](https://pillow.readthedocs.io/en/stable/installation/python-support.html)
