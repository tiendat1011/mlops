# Hướng Dẫn Triển Khai Teleport trên Private K8s với Tailscale Funnel

> **Teleport v18.x** | **Tailscale Funnel** | **Domain: `teleport-funnel.taild817b.ts.net`**

## Kiến Trúc Tổng Quan

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────────────────────────┐
│   Client      │────▶│ Tailscale Funnel     │────▶│  Private K8s Cluster (ns-teleport)   │
│  (tsh / web)  │    │ Relay (TLS term.)    │    │                                      │
└──────────────┘     └─────────────────────┘     │  ┌──────────────┐  ┌──────────────┐  │
                          ▲                       │  │ TS Operator  │  │  Teleport    │  │
                          │ Encrypted TCP proxy   │  │  (Ingress)   │─▶│  (ClusterIP) │  │
                          └───────────────────────│  └──────────────┘  └──────┬───────┘  │
                                                  │                          │          │
                                                  │         ┌────────────────┼────────┐ │
                                                  │         ▼                ▼        ▼ │
                                                  │   ┌─────────┐   ┌──────────┐  ┌────┐│
                                                  │   │ MariaDB │   │PostgreSQL│  │ CH ││
                                                  │   │  MySQL  │   │          │  │    ││
                                                  │   └─────────┘   └──────────┘  └────┘│
                                                  └──────────────────────────────────────┘
```

---

## Bước 0: Chuẩn Bị

### Yêu cầu
- `kubectl` đã cấu hình kết nối tới K8s Cluster
- `helm` v3.x đã cài đặt
- Tài khoản **Tailscale** (https://login.tailscale.com) — Free plan OK

### Cài đặt tsh CLI (Teleport Client)

```bash
# Linux (amd64) - v18.x
curl -O https://cdn.teleport.dev/teleport-v18.7.1-linux-amd64-bin.tar.gz
tar xzf teleport-v18.7.1-linux-amd64-bin.tar.gz
sudo mv teleport/tsh /usr/local/bin/

# macOS
brew install teleport
```

---

## Bước 1: Cấu hình Tailscale ACL & OAuth

### 1.1 Cấu hình ACL Policy

Vào **Tailscale Admin Console → Access Controls → Policy File**, thêm:

```jsonc
{
  // ... existing config ...

  "tagOwners": {
    "tag:k8s-operator": [],
    "tag:k8s": ["tag:k8s-operator"]
  },

  "nodeAttrs": [
    {
      "target": ["tag:k8s"],
      "attr": ["funnel"]
    }
  ],

  // Cho phép tag:k8s truy cập internet (cho Funnel)
  "acls": [
    // ... existing ACLs ...
    {
      "action": "accept",
      "src": ["tag:k8s"],
      "dst": ["autogroup:internet:*"]
    }
  ]
}
```

### 1.2 Tạo OAuth Client

1. Vào **Tailscale Admin Console → Settings → Trust credentials → OAuth clients**
2. Click **"Generate OAuth client..."**
3. Chọn scopes: **Devices Core** (Write), **Auth Keys** (Write), **Services** (Write)
4. Chọn tag: **`tag:k8s-operator`**
5. Lưu lại **Client ID** và **Client Secret**

### 1.3 Ghi nhận Tailnet Name

Tailnet name: **`taild817b.ts.net`**

> Domain Teleport: **`teleport-funnel.taild817b.ts.net`**
> (đã cập nhật trong `values.yaml`)

---

## Bước 3: Deploy trên Kubernetes

### 3.1 Tạo Namespace

```bash
kubectl apply -f infrastructure/teleport/namespace.yaml
```

### 3.2 Cài đặt Tailscale K8s Operator

```bash
# Thêm Helm repo
helm repo add tailscale https://pkgs.tailscale.com/helmcharts
helm repo update

# Install operator
# Thay <CLIENT_ID> và <CLIENT_SECRET> bằng OAuth credentials ở Bước 1.2
helm upgrade --install tailscale-operator tailscale/tailscale-operator \
  --namespace=tailscale \
  --create-namespace \
  --set-string oauth.clientId="<CLIENT_ID>" \
  --set-string oauth.clientSecret="<CLIENT_SECRET>" \
  --wait
```

### 3.3 Kiểm tra Operator

```bash
kubectl get pods -n tailscale

# Output mong đợi:
# NAME                                  READY   STATUS    RESTARTS   AGE
# operator-xxxxxxxxx-xxxxx              1/1     Running   0          1m
```

### 3.4 Deploy Teleport bằng Helm

```bash
# Thêm Helm repo
helm repo add teleport https://charts.releases.teleport.dev
helm repo update

# ⚠️ Nếu đã có release cũ, dùng upgrade thay vì install
helm upgrade --install teleport teleport/teleport-cluster \
  --namespace ns-teleport \
  --values infrastructure/teleport/values.yaml \
  --version 18.7.1 \
  --wait
```

### 3.5 Kiểm tra Teleport Pods

```bash
kubectl get pods -n ns-teleport

# Output mong đợi:
# NAME                              READY   STATUS    RESTARTS   AGE
# teleport-auth-xxxxxxxxx-xxxxx     1/1     Running   0          2m
# teleport-proxy-xxxxxxxxx-xxxxx    1/1     Running   0          2m
```

### 3.6 Tạo Admin User

```bash
kubectl exec -it deployment/teleport-auth -n ns-teleport -- \
  tctl users add admin --roles=editor,access,auditor \
  --logins=root,admin
```

> Output sẽ có **signup link**. Lưu lại, sẽ dùng sau khi Funnel hoạt động.

### 3.7 Apply Tailscale Funnel Ingress

```bash
kubectl apply -f infrastructure/teleport/tailscale-ingress.yaml
```

### 3.8 Kiểm tra Ingress

```bash
kubectl get ingress -n ns-teleport

# Output mong đợi (sau 1-2 phút):
# NAME               CLASS       HOSTS   ADDRESS                                    PORTS     AGE
# teleport-funnel    tailscale   *       teleport-funnel.taild817b.ts.net           80, 443   1m
```

> ⚠️ Cột **ADDRESS** sẽ hiển thị domain `*.ts.net`. Đây là URL truy cập Teleport.

### 3.9 Truy cập Web UI

Mở trình duyệt: **https://teleport-funnel.taild817b.ts.net**

> Nếu thấy trang login Teleport → Funnel đã hoạt động! 🎉
> Dùng signup link từ bước 3.6 để tạo password + 2FA lần đầu.

---

## Bước 4: Cấu Hình Database Access

### 4.1 Tạo Database Resources qua tctl

```bash
kubectl exec -it deployment/teleport-auth -n ns-teleport -- \
  tctl create -f /dev/stdin <<EOF
kind: db
version: v3
metadata:
  name: mariadb-internal
  description: "MariaDB - Internal Database"
  labels:
    env: production
    engine: mariadb
spec:
  protocol: mysql
  uri: "mariadb.ns-db.svc.cluster.local:3306"
EOF

kubectl exec -it deployment/teleport-auth -n ns-teleport -- \
  tctl create -f /dev/stdin <<EOF
kind: db
version: v3
metadata:
  name: mysql-internal
  description: "MySQL - Internal Database"
  labels:
    env: production
    engine: mysql
spec:
  protocol: mysql
  uri: "mysql.ns-db.svc.cluster.local:3306"
EOF

kubectl exec -it deployment/teleport-auth -n ns-teleport -- \
  tctl create -f /dev/stdin <<EOF
kind: db
version: v3
metadata:
  name: postgresql-internal
  description: "PostgreSQL - Internal Database"
  labels:
    env: production
    engine: postgresql
spec:
  protocol: postgres
  uri: "postgresql.ns-db.svc.cluster.local:5432"
EOF

kubectl exec -it deployment/teleport-auth -n ns-teleport -- \
  tctl create -f /dev/stdin <<EOF
kind: db
version: v3
metadata:
  name: clickhouse-internal
  description: "ClickHouse - Internal Database (Native Protocol)"
  labels:
    env: production
    engine: clickhouse
spec:
  protocol: clickhouse
  uri: "clickhouse.ns-db.svc.cluster.local:9440"
  tls:
    mode: verify-full
EOF
```

### 4.2 Tạo DB Access Role

```bash
kubectl exec -it deployment/teleport-auth -n ns-teleport -- \
  tctl create -f /dev/stdin <<EOF
kind: role
version: v7
metadata:
  name: db-access
spec:
  allow:
    db_labels:
      env: production
    db_names:
      - "*"
    db_users:
      - "*"
    rules:
      - resources: [db]
        verbs: [list, read]
EOF
```

### 4.3 Gán role cho user

```bash
kubectl exec -it deployment/teleport-auth -n ns-teleport -- \
  tctl users update admin --set-roles=editor,access,auditor,db-access
```

---

## Bước 5: Sử Dụng tsh Client (Máy Local)

### 5.1 Đăng nhập Teleport

```bash
tsh login --proxy=teleport-funnel.taild817b.ts.net --user=admin
```

### 5.2 Liệt kê Database

```bash
tsh db ls
```

### 5.3 Kết nối Database

### 5.3 Kết nối Database

Teleport hỗ trợ 3 phương thức kết nối chính:
1. **Dùng CLI** (`tsh db connect`): Tự động cấu hình mTLS, tiện nhất cho gõ lệnh nhanh.
2. **Dùng GUI Client** (DBeaver, DataGrip, pgAdmin): Dùng `tsh proxy db --tunnel` để tạo cleartext local proxy.
3. **Từ Application Code**: Dùng Machine ID (tbot) hoặc Local Proxy.

#### Cách 1: Kết nối trực tiếp qua CLI (`tsh db connect`)

Phương pháp này tự động gọi native CLI client (mysql, psql, clickhouse-client) và tự nhúng Client Certificate.

```bash
# MariaDB
tsh db connect mariadb-internal --db-user=teleport-admin --db-name=mydb

# MySQL
tsh db connect mysql-internal --db-user=teleport-admin --db-name=mydb

# PostgreSQL
tsh db connect postgresql-internal --db-user=teleport-admin --db-name=mydb

# ClickHouse (Dùng Native Protocol)
tsh db connect clickhouse-internal --db-user=default --db-name=default
```

#### Cách 2: Kết nối qua Database GUI Clients (DBeaver, DataGrip, TablePlus)

Các GUI Client không hỗ trợ nạp tự động mTLS certificate của Teleport. Do đó, bạn cần dùng lệnh `tsh proxy db` với cờ `--tunnel` (tạo kênh cleartext ở localhost, tsh sẽ tự bọc mTLS khi gửi lên cluster).

**Bước 1: Chạy Local Proxy (mở terminal và để chạy ngầm)**
```bash
# Mở proxy cho MariaDB ở port 13306
tsh proxy db --tunnel --db-user=teleport-admin --db-name=mydb --port=13306 mariadb-internal

# Mở proxy cho PostgreSQL ở port 15432
tsh proxy db --tunnel --db-user=teleport-admin --db-name=mydb --port=15432 postgresql-internal

# Mở proxy cho ClickHouse ở port 19000
tsh proxy db --tunnel --db-user=default --db-name=default --port=19000 clickhouse-internal
```

**Bước 2: Cấu hình connection trong GUI Client (VD: DBeaver)**
- **Host**: `127.0.0.1` (hoặc `localhost`)
- **Port**: `13306` (hoặc port bạn đã cấu hình ở Bước 1)
- **Database Name**: `mydb`
- **User**: `teleport-admin` (username bạn đã chọn trong lệnh proxy)
- **Password**: *Để trống!* (Xác thực bằng mTLS do proxy xử lý)
- **SSL**: Tắt hoàn toàn (Disable)

#### Cách 3: Kết nối từ Application Code / CI/CD Pipeline

Application không thể dùng `tsh login`. Giải pháp là dùng **Teleport Machine ID (tbot)**.

**Mô hình cấp chứng chỉ định kỳ (File-based):**
1. Cài đặt quá trình nền `tbot` trên máy chủ application
2. Cấu hình `tbot` sinh ra TLS certificates (`tls.crt`, `tls.key`, `teleport.ca`) và tự làm mới mỗi x giờ.
3. Code application nạp các cert này vào connection string:
   ```python
   # Ví dụ Python (psycopg2) cho PostgreSQL
   import psycopg2
   conn = psycopg2.connect(
       host="teleport-funnel.taild817b.ts.net",
       port=5432,
       database="mydb",
       user="teleport-admin",
       sslmode="verify-full",
       sslrootcert="/path/to/tbot/teleport.ca",
       sslcert="/path/to/tbot/tls.crt",
       sslkey="/path/to/tbot/tls.key"
   )
   ```

**Mô hình Local Proxy (tbot proxy):**
`tbot` tự động mở 1 cổng localhost, application kết nối vào localhost như database bình thường (giống Cách 2 nhưng tự động 100%).
```yaml
# tbot.yaml
destinations:
  - directory: /opt/machine-id
    database:
      service: postgresql-internal
    proxy:
      db_listen_address: 127.0.0.1:5432
      tunnel: true
```
Code chỉ cần: `postgres://teleport-admin@127.0.0.1:5432/mydb`

### 5.4 Ngắt kết nối

```bash
tsh db logout          # Logout tất cả DB
tsh logout             # Logout Teleport
```

---

## Troubleshooting

### Tailscale Operator không chạy

```bash
kubectl get pods -n tailscale
kubectl logs -n tailscale -l app.kubernetes.io/name=tailscale-operator --tail=50
```

### Ingress không có ADDRESS

```bash
# Kiểm tra ingress events
kubectl describe ingress teleport-funnel -n ns-teleport

# Kiểm tra tailscale proxy pod (tạo bởi operator)
kubectl get pods -n tailscale --show-labels

# Kiểm tra ACL có cho phép funnel
# → Tailscale Admin Console → Access Controls
```

### Không truy cập được Web UI

```bash
# Kiểm tra Teleport pods
kubectl get pods -n ns-teleport
kubectl logs -n ns-teleport -l app=teleport --tail=50

# Kiểm tra service
kubectl get svc -n ns-teleport
```

### tsh login lỗi

```bash
# Kiểm tra DNS resolve
nslookup teleport-funnel.taild817b.ts.net

# Thử curl
curl -vvv https://teleport-funnel.taild817b.ts.net 2>&1 | head -30
```

---

## Tóm Tắt File Structure

```
infrastructure/teleport/
├── namespace.yaml              # Namespace ns-teleport
├── values.yaml                 # Helm values (publicAddr = *.ts.net)
├── tailscale-ingress.yaml      # Ingress + Funnel annotation
├── db-mariadb.yaml             # Database resource - MariaDB
├── db-mysql.yaml               # Database resource - MySQL
├── db-postgresql.yaml          # Database resource - PostgreSQL
├── db-clickhouse.yaml          # Database resource - ClickHouse
├── kustomization.yaml          # Kustomize aggregation
└── DEPLOYMENT_GUIDE.md         # Hướng dẫn này
```

> **Note**: Các file `cloudflared-*` là legacy từ cấu hình Cloudflare Tunnel trước đó, có thể xoá khi không cần.
