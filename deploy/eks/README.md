# Deploy no EKS

Manifestos K8s para rodar o dashboard Streamlit no Amazon EKS. Inclui namespace, ConfigMap, Secret de exemplo, Deployment, Service e PVC para `/app/data` (onde fica o `finops.db`).

## Componentes
- `namespace.yaml` – namespace `finops`
- `configmap.yaml` – valores padrão (model, cache, log)
- `secret.sample.yaml` – placeholder do `OPENAI_API_KEY`
- `pvc.yaml` – volume `gp2` 1Gi para `data/`
- `deployment.yaml` – 2 réplicas, porta 8501, probes HTTP
- `service.yaml` – `LoadBalancer` expondo porta 80
- `kustomization.yaml` – aplica tudo via `kubectl apply -k`

## Build e push da imagem (ECR)
```bash
AWS_REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REPO=finops-dashboard

aws ecr create-repository --repository-name $REPO --region $AWS_REGION || true
docker build -t $REPO:latest .
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
docker tag $REPO:latest $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO:latest
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO:latest
```

Atualize `deploy/eks/deployment.yaml` com o nome da imagem gerada (ECR).

## Criar Secret com a chave da OpenAI
Use um arquivo dedicado (copie o sample) ou crie via CLI:
```bash
kubectl create namespace finops
kubectl create secret generic finops-secrets \
  --from-literal=OPENAI_API_KEY=sk-xxxx \
  -n finops
```
(Se preferir YAML, copie `secret.sample.yaml` para `secret.yaml`, preencha a chave e aplique com `kubectl apply -f secret.yaml`.)

## Deploy
```bash
# aplica ConfigMap, PVC, Deployment e Service
kubectl apply -k deploy/eks

# acompanhar rollout
kubectl rollout status deployment/finops-dashboard -n finops

# URL pública
kubectl get svc finops-dashboard -n finops
```

## Notas
- O PVC usa `gp2`; ajuste `storageClassName` se o cluster tiver outro default (ex.: `gp3`).
- Monte um volume em `/app/data` para persistir uploads e o `finops.db`. Sem isso, dados somem a cada recriação de pod.
- As probes usam o path `/`; se alterar a porta, ajuste `service.yaml` e as probes em `deployment.yaml`.
