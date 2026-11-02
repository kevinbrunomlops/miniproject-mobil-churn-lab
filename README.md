# Mobil Churn – MLOps Mini Project

## 1. Projektöversikt

Detta miniprojekt bygger vidare på [mobil-churn-laboration](https://github.com/kevinbrunomlops/mobil-churn-laboration), där vi utvecklade en CI-pipeline för en maskininlärningsmodell som förutsäger kundbortfall (churn).

Syftet med miniprojektet är att vidareutveckla lösningen till en driftsatt ML-tjänst med hjälp av **Docker, GitHub Actions, FastAPI och Kubernetes**.

Projektet omfattar automatiserad kvalitetssäkring, modellträning, versionshantering, containerisering samt utrullning och rollback i både lokal och molnbaserad Kubernetes-miljö.

## 2. CI/CD – Från kodändring till driftsatt modell

Pipelinen är implementerad med GitHub Actions och består av följande steg:

1. **Kodändring:** En push eller pull request kan starta CI-pipelinen beroende på vilka filer som ändrats.
2. **Tester:** Pytest kontrollerar funktionalitet och modellkrav i Python 3.11, 3.12 och 3.13.
3. **Datavalidering:** Pandera kontrollerar att träningsdata följer det förväntade schemat.
4. **Modellträning:** En scikit-learn-modell tränas och sparas som en `.joblib`-fil.
5. **Kvalitetsgrind:** Modellen måste uppnå ROC AUC ≥ 0.70.
6. **Docker:** Den godkända modellen paketeras tillsammans med FastAPI i en container-image.
7. **GHCR:** Imagen publiceras i GitHub Container Registry med commitens SHA som versionstagg.
8. **Utrullning:** En separat GitHub Actions-workflow kan manuellt startas för att distribuera en godkänd version till Kubernetes i molnet.

Produktionsutrullningen använder `workflow_dispatch` och kräver manuellt godkännande. Workflowet kontrollerar att versionen har passerat CI, uppdaterar Kubernetes Deployment och verifierar att utrullningen lyckas.

Detta ger spårbarhet från **Git-commit → tränad modell → Docker-image → Kubernetes**.

## 3. Docker och FastAPI

Modellen exponeras som en REST API-tjänst med FastAPI.

API:et innehåller bland annat:

- `GET /health` – kontrollerar tjänstens hälsa och visar aktiv modellversion.
- `GET /model-info` – visar information om modellen.
- `POST /predict` – tar emot kunddata och returnerar en churn-prediktion.

Projektets `Dockerfile` bygger en image som innehåller applikationen, dess beroenden och den tränade modellartefakten. Containern startar FastAPI via Uvicorn på port 8000.

Docker används för att paketera tjänsten med dess beroenden så att samma image kan köras i olika miljöer.

Imagen byggs för både `linux/amd64` och `linux/arm64`, vilket gör den kompatibel med GitHub Actions-miljön och det ARM64-baserade molnklustret.

Varje publicerad image taggas med en fullständig commit-SHA i stället för `latest`. Därmed går det att identifiera exakt vilken kodversion som ligger bakom en driftsatt modell.

## 4. Kubernetes – Deployment och Service

Kubernetes används för att köra och hantera den containeriserade ML-tjänsten.

Konfigurationen finns i katalogen `k8s/`:

- **`deployment.yaml`** – definierar containern, antal repliker, resursgränser och hälsokontroller.
- **`service.yaml`** – skapar en intern ClusterIP Service som gör API:et åtkomligt inom klustret.

Deployment använder CPU- och minnesbegränsningar samt följande probes mot `/health`:

- **Startup probe:** Kontrollerar att applikationen har startat.
- **Readiness probe:** Avgör när podden är redo att ta emot trafik.
- **Liveness probe:** Kontrollerar om containern behöver startas om.

Dessa kontroller hjälper Kubernetes att hantera tjänstens livscykel och genomföra säkrare uppdateringar.

## 5. Lokal miljö och molnmiljö

Projektet har distribuerats i två Kubernetes-miljöer.

| Miljö | Teknik | Syfte |
|---|---|---|
| Lokal | kind + Docker Desktop | Testa Kubernetes-manifest, API, rolling update och rollback |
| Moln | `mlops-ht26`, namespace `kevin-bruno` | Verifiera att den publicerade Docker-imagen fungerar i en produktionsliknande miljö |

**kind** (Kubernetes in Docker) används för att skapa ett lokalt Kubernetes-kluster. Det gör det möjligt att testa Deployment, Service och utrullningsstrategier utan att behöva använda molnresurser.

**Molnklustret** används för att verifiera den publicerade GHCR-imagen i en separat Kubernetes-miljö med resursbegränsningar och åtkomstkontroll.

I båda miljöerna har tjänstens funktionalitet och Kubernetes-utrullning testats.

## 6. Val av utrullningsstrategi – RollingUpdate

Projektet använder Kubernetes standardstrategi **RollingUpdate**.

Vid en uppdatering startar Kubernetes en pod med den nya versionen och väntar tills den är redo innan den gamla podden tas bort.

Deployment är konfigurerad med:

- `maxSurge: 1` – tillåter en extra pod under uppdateringen.
- `maxUnavailable: 0` – behåller önskat antal tillgängliga repliker under utrullningen.
- Readiness probe – kontrollerar att den nya podden är redo.

### Varför RollingUpdate framför Blue/Green eller Canary?

**RollingUpdate** valdes eftersom projektet består av en mindre ML-tjänst i en resursbegränsad Kubernetes-miljö. Strategin har inbyggt stöd i Kubernetes, kräver relativt lite konfiguration och möjliggör rollback.

**Blue/Green** hade krävt två parallella miljöer, vilket ökar resursbehovet men ger möjlighet till snabb växling mellan versionerna.

**Canary** hade gjort det möjligt att gradvis styra en mindre andel trafik till en ny modellversion, men hade krävt mer avancerad trafikstyrning och övervakning.

RollingUpdate bedömdes därför ge den bästa balansen mellan enkelhet, resurser och tillgänglighet för projektets omfattning.

## 7. Modelluppdatering och rollback

För att demonstrera versionshantering och rollback användes två modellartefakter som publicerats i GHCR efter godkända CI-körningar.

| | Modell A | Modell B |
|---|---|---|
| Commit-SHA | `a37394cb…` | `165c92d1…` |
| ROC AUC | 0.7887 | 0.7887 |
| Accuracy | 0.824 | 0.824 |
| CI-status | Godkänd | Godkänd |

Modellfilerna hade olika SHA-256-hashvärden, vilket bekräftar att de är olika artefakter på byte-nivå. De har däremot samma rapporterade mätvärden och träningsdata.

### Genomförd demonstration

1. **Modell A** kördes i molnklustret och verifierades.
2. **Modell B** distribuerades med `kubectl set image`.
3. Kubernetes genomförde en lyckad rolling update.
4. API:ets `/health` bekräftade att Modell B kördes.
5. `kubectl rollout undo` användes för att återställa Modell A.
6. Rollback lyckades och `/health` bekräftade att Modell A återigen kördes.

Exempel på kommandon:

```bash
# Kontrollera utrullning
kubectl --context mlops-ht26 -n kevin-bruno \
  rollout status deployment/churn-api

# Återställ tidigare version
kubectl --context mlops-ht26 -n kevin-bruno \
  rollout undo deployment/churn-api

# Kontrollera revisionshistorik
kubectl --context mlops-ht26 -n kevin-bruno \
  rollout history deployment/churn-api
```

**Resultat:** Demonstrationen visade att en ny, CI-godkänd modellartefakt kunde rullas ut och att den tidigare versionen kunde återställas. Modellversionerna verifierades genom API:ets `/health`-endpoint.

## 8. Resultat och vidareutveckling

Miniprojektet demonstrerar ett MLOps-flöde från kodändring och modellträning till en containeriserad ML-tjänst i Kubernetes.

De viktigaste resultaten är:

- Automatiserade tester, datavalidering och kvalitetsgrind.
- Spårbara modellartefakter och Docker-images kopplade till Git-commits.
- Fungerande API i både lokalt och molnbaserat Kubernetes-kluster.
- Manuell, godkännandestyrd produktionsutrullning via GitHub Actions.
- Verifierad rolling update och rollback mellan två modellartefakter.

Möjliga förbättringar är automatiserad staging, utökad övervakning, striktare Kubernetes-säkerhetsinställningar och tydligare hantering av konfigurationsdrift mellan YAML-manifest och den körande miljön.