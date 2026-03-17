# Jenkins Build Trigger với GitLab Webhook & Outlook Approval (No-Login)

Hướng dẫn thiết lập Jenkins tự động trigger build khi nhánh `prod` trên GitLab được merge/push code, kết hợp quy trình phê duyệt qua **Outlook Email** — **không cần đăng nhập Jenkins** để approve/reject.

---

## Tổng quan kiến trúc

```
┌─────────┐    Webhook     ┌─────────┐    Email       ┌──────────┐
│  GitLab  │──────────────▶│ Jenkins  │──────────────▶│  Outlook  │
│  (prod)  │  push/merge   │ Pipeline │  Approve URL  │  Mailbox  │
└─────────┘                └────┬─────┘               └────┬──────┘
                                │                          │
                                │  ◀───────────────────────┘
                                │  Click link (NO LOGIN!)
                                │
                         ┌──────┴──────┐
                         │   Approve?  │
                         ├─────┬───────┤
                     YES │     │ NO/Timeout
                         ▼     ▼
                    ┌────────┐ ┌──────────┐
                    │ Deploy │ │  Abort   │
                    │  Prod  │ │ Pipeline │
                    └────────┘ └──────────┘
```

**Luồng hoạt động:**
1. Developer merge MR vào nhánh `prod` trên GitLab
2. GitLab gửi webhook → Jenkins trigger pipeline
3. Jenkins build → test → **gửi email chứa link Approve/Reject**
4. Approver nhận email Outlook → **click link trực tiếp** (không cần login Jenkins)
5. ✅ Approve → deploy tiếp | ❌ Reject → pipeline dừng | ⏰ Timeout → tự động abort

> [!IMPORTANT]
> Khác biệt chính so với cách dùng `input()` thông thường: sử dụng **Webhook Step Plugin** để tạo URL tạm thời — cho phép approve qua 1 click mà **không cần tài khoản Jenkins**.

---

## Yêu cầu

| Thành phần | Yêu cầu |
|---|---|
| **Jenkins** | >= 2.387 (LTS) |
| **Plugins** | GitLab Plugin, Email Extension, **Webhook Step**, Pipeline, Credentials |
| **GitLab** | Quyền Maintainer trở lên |
| **Outlook/SMTP** | Tài khoản SMTP (Office 365 / Exchange) |
| **Network** | Jenkins public URL (hoặc qua Cloudflare Tunnel) |

---

## Bước 1: Cài đặt Jenkins Plugins

Vào **Manage Jenkins → Plugins → Available plugins**, cài đặt:

| Plugin | ID | Mục đích |
|---|---|---|
| GitLab Plugin | `gitlab-plugin` | Nhận webhook từ GitLab |
| Email Extension | `email-ext` | Gửi email qua Outlook SMTP |
| **Webhook Step** | `webhook-step` | **Tạo callback URL không cần login** |
| Pipeline | `workflow-aggregator` | Hỗ trợ Jenkinsfile |
| Credentials Binding | `credentials-binding` | Quản lý secrets |

> [!CAUTION]
> Plugin **Webhook Step** (`webhook-step`) là plugin quan trọng nhất cho flow no-login. Hãy chắc chắn nó đã được cài.

Sau khi cài → **Restart Jenkins**.

---

## Bước 2: Cấu hình SMTP cho Outlook

### 2.1 Cấu hình System Email

Vào **Manage Jenkins → System**:

#### Mục "Jenkins Location"
```
System Admin e-mail address: devops-team@yourcompany.com
```

#### Mục "Extended E-mail Notification"

| Field | Value |
|---|---|
| SMTP server | `smtp.office365.com` |
| SMTP Port | `587` |
| Use TLS | ✅ Checked |
| Credentials | Username/password Outlook |
| Default Content Type | `text/html` |
| Default Recipients | `approver@yourcompany.com` |

> [!TIP]
> Nếu dùng **Microsoft 365** với MFA → tạo **App Password**:
> 1. Đăng nhập [https://myaccount.microsoft.com](https://myaccount.microsoft.com)
> 2. **Security → App Passwords → Create**
> 3. Sử dụng App Password thay cho mật khẩu thường

### 2.2 Thêm SMTP Credentials

**Manage Jenkins → Credentials → System → Global → Add Credentials**:

```
Kind:     Username with password
Username: devops@yourcompany.com
Password: <App Password>
ID:       outlook-smtp-creds
```

---

## Bước 3: Kết nối Jenkins với GitLab

### 3.1 Tạo Access Token trên GitLab

1. **GitLab → Settings → Access Tokens**
2. Tạo token với quyền `api` + `read_repository`
3. Copy token

### 3.2 Thêm GitLab Token vào Jenkins

**Manage Jenkins → Credentials → Add Credentials**:

```
Kind:       GitLab API token
API Token:  <paste GitLab token>
ID:         gitlab-api-token
```

### 3.3 Cấu hình GitLab Connection

**Manage Jenkins → System → GitLab**:

| Field | Value |
|---|---|
| Connection name | `gitlab-server` |
| GitLab host URL | `https://gitlab.yourcompany.com` |
| Credentials | Chọn `gitlab-api-token` |

Click **Test Connection** → phải hiện **"Success"**.

---

## Bước 4: Tạo Jenkins Pipeline

### 4.1 Tạo Pipeline Job

**New Item → Pipeline**, đặt tên: `prod-deployment-pipeline`

### 4.2 Cấu hình Build Trigger

Trong **Build Triggers**:

```
☑ Build when a change is pushed to GitLab
  GitLab webhook URL: https://jenkins.yourcompany.com/project/prod-deployment-pipeline

  Enabled GitLab triggers:
  ☑ Push Events
  ☑ Accepted Merge Request Events

  Filter branches by name:
    Include: prod
```

> [!IMPORTANT]
> Ghi lại **GitLab webhook URL** — cần cho Bước 5.

### 4.3 Tạo Secret Token

**Build Triggers → Advanced → Secret token** → **Generate** → Copy token.

---

## Bước 5: Cấu hình Webhook trên GitLab

**GitLab → Project → Settings → Webhooks → Add webhook**:

| Field | Value |
|---|---|
| URL | `https://jenkins.yourcompany.com/project/prod-deployment-pipeline` |
| Secret token | Token từ Bước 4.3 |
| Trigger | ✅ Push events, ✅ Merge request events |
| Enable SSL | ✅ |
| Branch filter | `prod` |

Click **Test → Push events** → phải nhận 200 OK.

> [!NOTE]
> Nếu Jenkins trong mạng nội bộ → dùng **Cloudflare Tunnel** hoặc cấu hình GitLab cho phép outbound requests tới local network.

---

## Bước 6: Jenkinsfile với Webhook Approval (Không cần Login)

### Cách hoạt động của Webhook Step Plugin

```
Pipeline chạy → registerWebhook() tạo URL tạm thời
                 ↓
Email gửi URL đó cho approver
                 ↓
Approver click link trong Outlook → HTTP POST tới webhook URL
                 ↓
waitForWebhook() nhận response → pipeline tiếp tục hoặc dừng
```

**Ưu điểm:**
- ✅ Không cần login Jenkins để approve
- ✅ URL tạm thời, tự hủy sau khi dùng (bảo mật)
- ✅ Hoạt động với bất kỳ email client nào
- ✅ Hỗ trợ timeout tự động

### Jenkinsfile hoàn chỉnh

```groovy
pipeline {
    agent any

    environment {
        GITLAB_PROJECT     = 'your-group/your-project'
        DEPLOY_ENV         = 'production'
        APPROVER_EMAIL     = 'manager@yourcompany.com'
        APPROVAL_TIMEOUT   = '4'  // Timeout tính bằng giờ
    }

    options {
        gitLabConnection('gitlab-server')
        timeout(time: 8, unit: 'HOURS')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    triggers {
        gitlab(
            triggerOnPush: true,
            triggerOnMergeRequest: true,
            branchFilterType: 'NameBasedFilter',
            includeBranchesSpec: 'prod'
        )
    }

    stages {
        // ═══════════════════════════════════════
        // Stage 1: Checkout
        // ═══════════════════════════════════════
        stage('Checkout') {
            steps {
                checkout scm
                updateGitlabCommitStatus name: 'build', state: 'running'
                script {
                    env.GIT_SHORT_COMMIT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.GIT_AUTHOR       = sh(script: 'git log -1 --format="%an"', returnStdout: true).trim()
                    env.GIT_MSG          = sh(script: 'git log -1 --format="%s"', returnStdout: true).trim()
                }
            }
        }

        // ═══════════════════════════════════════
        // Stage 2: Build
        // ═══════════════════════════════════════
        stage('Build') {
            steps {
                echo "🔨 Building ${GITLAB_PROJECT}..."
                sh '''
                    # === CUSTOMIZE: Thêm lệnh build ===
                    # docker build -t your-registry/app:${GIT_SHORT_COMMIT} .
                    # docker push your-registry/app:${GIT_SHORT_COMMIT}
                    echo "Build completed"
                '''
            }
        }

        // ═══════════════════════════════════════
        // Stage 3: Test
        // ═══════════════════════════════════════
        stage('Test') {
            steps {
                echo "🧪 Running tests..."
                sh '''
                    # === CUSTOMIZE: Thêm lệnh test ===
                    # pytest tests/ --junitxml=test-results.xml
                    echo "Tests passed"
                '''
            }
        }

        // ═══════════════════════════════════════
        // Stage 4: Approval qua Outlook (KHÔNG CẦN LOGIN)
        // ═══════════════════════════════════════
        stage('Approval via Outlook') {
            steps {
                script {
                    // 1. Tạo 2 webhook URLs tạm thời (approve & reject)
                    def approveHook = registerWebhook()
                    def rejectHook  = registerWebhook()

                    def approveUrl = approveHook.getURL()
                    def rejectUrl  = rejectHook.getURL()

                    echo "📧 Sending approval email to ${APPROVER_EMAIL}..."
                    echo "   Approve URL: ${approveUrl}"
                    echo "   Reject  URL: ${rejectUrl}"

                    // 2. Gửi email với 2 nút Approve / Reject
                    emailext(
                        to: "${APPROVER_EMAIL}",
                        subject: "🚀 [APPROVAL] Deploy ${GITLAB_PROJECT} #${BUILD_NUMBER} → ${DEPLOY_ENV}",
                        mimeType: 'text/html',
                        body: """
                        <html>
                        <body style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; background: #f5f5f5;">
                            <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 30px; border-radius: 12px 12px 0 0; color: white;">
                                <h2 style="margin:0;">🚀 Deployment Approval Required</h2>
                                <p style="margin:5px 0 0; opacity:0.85; font-size:14px;">A new deployment is waiting for your review</p>
                            </div>

                            <div style="background: #fff; padding: 25px; border: 1px solid #e0e0e0;">
                                <table style="width:100%; border-collapse:collapse; font-size:14px;">
                                    <tr>
                                        <td style="padding:10px 0; color:#666; width:120px;"><strong>Project</strong></td>
                                        <td>${GITLAB_PROJECT}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:10px 0; color:#666;"><strong>Branch</strong></td>
                                        <td><code style="background:#e8f5e9; padding:2px 8px; border-radius:3px; color:#2e7d32;">prod</code></td>
                                    </tr>
                                    <tr>
                                        <td style="padding:10px 0; color:#666;"><strong>Environment</strong></td>
                                        <td>${DEPLOY_ENV}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:10px 0; color:#666;"><strong>Build</strong></td>
                                        <td>#${BUILD_NUMBER}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:10px 0; color:#666;"><strong>Commit</strong></td>
                                        <td><code style="background:#f0f0f0; padding:2px 8px; border-radius:3px;">${env.GIT_SHORT_COMMIT}</code></td>
                                    </tr>
                                    <tr>
                                        <td style="padding:10px 0; color:#666;"><strong>Author</strong></td>
                                        <td>${env.GIT_AUTHOR}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:10px 0; color:#666;"><strong>Message</strong></td>
                                        <td><em>${env.GIT_MSG}</em></td>
                                    </tr>
                                </table>
                            </div>

                            <div style="background: #fff; padding: 25px; border: 1px solid #e0e0e0; border-top: none; text-align: center;">
                                <p style="color: #555; font-size: 14px; margin-bottom: 20px;">
                                    Click a button below to approve or reject — <strong>no Jenkins login required</strong>.
                                </p>

                                <a href="${approveUrl}"
                                   style="background: #28a745; color: white; padding: 14px 40px;
                                          text-decoration: none; border-radius: 6px; font-weight: bold;
                                          font-size: 16px; display: inline-block; margin: 8px;">
                                    ✅ APPROVE
                                </a>

                                <a href="${rejectUrl}"
                                   style="background: #dc3545; color: white; padding: 14px 40px;
                                          text-decoration: none; border-radius: 6px; font-weight: bold;
                                          font-size: 16px; display: inline-block; margin: 8px;">
                                    ❌ REJECT
                                </a>
                            </div>

                            <div style="background: #fff; padding: 15px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 12px 12px; text-align: center;">
                                <p style="color: #aaa; font-size: 12px; margin: 0;">
                                    ⏰ This request will auto-expire in ${APPROVAL_TIMEOUT} hours if no action is taken.
                                </p>
                            </div>
                        </body>
                        </html>
                        """
                    )

                    // 3. Chờ response (với timeout tự động)
                    def approved = false
                    try {
                        timeout(time: APPROVAL_TIMEOUT.toInteger(), unit: 'HOURS') {
                            // Chờ song song: ai click trước thì dùng kết quả đó
                            def result = null

                            parallel(
                                'wait-approve': {
                                    def response = waitForWebhook(approveHook)
                                    result = 'APPROVED'
                                },
                                'wait-reject': {
                                    def response = waitForWebhook(rejectHook)
                                    result = 'REJECTED'
                                },
                                failFast: true
                            )

                            if (result == 'APPROVED') {
                                approved = true
                                echo "✅ Deployment APPROVED!"
                            }
                        }
                    } catch (err) {
                        if (!approved) {
                            // Gửi email thông báo timeout/reject
                            emailext(
                                to: "${APPROVER_EMAIL}",
                                subject: "⏰ [EXPIRED/REJECTED] Deploy ${GITLAB_PROJECT} #${BUILD_NUMBER}",
                                mimeType: 'text/html',
                                body: """
                                <html><body style="font-family:'Segoe UI',Arial; padding:20px;">
                                    <div style="background:#ffc107; padding:20px; border-radius:8px;">
                                        <h2 style="margin:0; color:#333;">⏰ Deployment Not Approved</h2>
                                    </div>
                                    <p><strong>Project:</strong> ${GITLAB_PROJECT}</p>
                                    <p><strong>Build:</strong> #${BUILD_NUMBER}</p>
                                    <p>The deployment was either rejected or timed out after ${APPROVAL_TIMEOUT} hours.</p>
                                </body></html>
                                """
                            )
                            error("❌ Deployment was rejected or timed out after ${APPROVAL_TIMEOUT} hours")
                        }
                    }
                }
            }
        }

        // ═══════════════════════════════════════
        // Stage 5: Deploy to Production
        // ═══════════════════════════════════════
        stage('Deploy to Production') {
            steps {
                echo "🚀 Deploying to ${DEPLOY_ENV}..."
                sh '''
                    echo "Deploying application..."
                    # === CUSTOMIZE: Thêm lệnh deploy ===
                    # kubectl set image deployment/app app=registry/app:${GIT_SHORT_COMMIT} -n production
                    # argocd app sync your-app --grpc-web
                '''
            }
        }

        // ═══════════════════════════════════════
        // Stage 6: Notification
        // ═══════════════════════════════════════
        stage('Notify') {
            steps {
                script {
                    emailext(
                        to: "${APPROVER_EMAIL}",
                        subject: "✅ [DEPLOYED] ${GITLAB_PROJECT} #${BUILD_NUMBER} → ${DEPLOY_ENV}",
                        mimeType: 'text/html',
                        body: """
                        <html><body style="font-family:'Segoe UI',Arial; padding:20px;">
                            <div style="background:#28a745; color:white; padding:20px; border-radius:8px;">
                                <h2 style="margin:0;">✅ Deployment Successful</h2>
                            </div>
                            <div style="padding:15px 0;">
                                <p><strong>Project:</strong> ${GITLAB_PROJECT}</p>
                                <p><strong>Commit:</strong> <code>${env.GIT_SHORT_COMMIT}</code></p>
                                <p><strong>Build:</strong> #${BUILD_NUMBER}</p>
                            </div>
                        </body></html>
                        """
                    )
                }
            }
        }
    }

    // ═══════════════════════════════════════
    // Post Actions
    // ═══════════════════════════════════════
    post {
        success {
            updateGitlabCommitStatus name: 'build', state: 'success'
        }
        failure {
            updateGitlabCommitStatus name: 'build', state: 'failed'
            emailext(
                to: "${APPROVER_EMAIL}",
                subject: "🔴 [FAILED] ${GITLAB_PROJECT} #${BUILD_NUMBER}",
                body: "Build failed. Check: ${BUILD_URL}console"
            )
        }
        aborted {
            updateGitlabCommitStatus name: 'build', state: 'canceled'
        }
    }
}
```

---

## Bước 7: Cấu hình nâng cao

### 7.1 Tùy chỉnh thời gian Timeout

Thay đổi biến `APPROVAL_TIMEOUT` trong `environment`:

```groovy
environment {
    APPROVAL_TIMEOUT = '2'   // 2 giờ
    // hoặc
    APPROVAL_TIMEOUT = '0.5' // 30 phút (dùng cho testing)
}
```

### 7.2 Nhiều người Approve

```groovy
stage('Multi-Approval') {
    steps {
        script {
            def approvers = [
                [email: 'tech-lead@company.com',  name: 'Tech Lead'],
                [email: 'manager@company.com',    name: 'Manager']
            ]

            approvers.each { approver ->
                def hook = registerWebhook()
                def hookUrl = hook.getURL()

                emailext(
                    to: approver.email,
                    subject: "🚀 [APPROVAL] ${approver.name} - Deploy #${BUILD_NUMBER}",
                    mimeType: 'text/html',
                    body: """
                        <p>Hi ${approver.name},</p>
                        <p>Click to approve:</p>
                        <a href="${hookUrl}" style="background:#28a745; color:white; padding:12px 30px; text-decoration:none; border-radius:5px;">
                            ✅ APPROVE
                        </a>
                    """
                )

                timeout(time: 4, unit: 'HOURS') {
                    waitForWebhook(hook)
                }
                echo "✅ ${approver.name} approved!"
            }
        }
    }
}
```

### 7.3 Kết hợp với ArgoCD

```groovy
stage('Deploy via ArgoCD') {
    steps {
        sh '''
            cd k8s-manifests/
            sed -i "s|image:.*|image: registry/app:${BUILD_NUMBER}|" deployment.yaml
            git add . && git commit -m "Deploy #${BUILD_NUMBER}" && git push origin main
            argocd app sync your-app --grpc-web
            argocd app wait your-app --health --grpc-web
        '''
    }
}
```

---

## Bước 8: Kiểm tra toàn bộ luồng

### Checklist

| # | Kiểm tra | Trạng thái |
|---|---|---|
| 1 | GitLab webhook gửi thành công (200 OK) | ☐ |
| 2 | Jenkins chỉ trigger khi push/merge vào `prod` | ☐ |
| 3 | Email approval gửi tới Outlook thành công | ☐ |
| 4 | **Click Approve trong email → deploy tiếp (KHÔNG cần login)** | ☐ |
| 5 | **Click Reject trong email → pipeline dừng** | ☐ |
| 6 | **Không click gì → timeout tự động abort** | ☐ |
| 7 | Email notification sau deploy thành công/thất bại | ☐ |

### Test thử

```bash
# 1. Tạo feature branch và push
git checkout -b feature/test-approval
echo "test" > test.txt
git add . && git commit -m "Test approval flow"
git push origin feature/test-approval

# 2. Tạo MR trên GitLab → merge vào prod

# 3. Kiểm tra:
#    - Jenkins pipeline được trigger?
#    - Email gửi tới Outlook?
#    - Click Approve → pipeline tiếp tục?
#    - Không click → timeout sau N giờ?
```

---

## Troubleshooting

### Webhook Step Plugin không hoạt động

```
Lỗi: "No such DSL method 'registerWebhook'"
→ Kiểm tra plugin Webhook Step đã cài chưa
→ Manage Jenkins → Plugins → Installed → tìm "Webhook Step"
→ Nếu chưa có: cài webhook-step plugin → restart Jenkins
```

### Click link trong email báo lỗi

```
Lỗi 404 khi click approve link:
→ Jenkins URL phải accessible từ bên ngoài (internet/VPN)
→ Kiểm tra Jenkins URL trong Jenkins Location settings
→ Nếu dùng reverse proxy → đảm bảo pass-through webhook paths

Lỗi: Link mở nhưng không có phản hồi:
→ Webhook Step cần HTTP POST. Một số email client mở link bằng GET.
→ Giải pháp: Dùng trang HTML trung gian (xem phần dưới)
```

### Trang HTML trung gian cho email clients chặn POST

Nếu Outlook mở link bằng GET thay vì POST, tạo trang HTML trung gian:

```groovy
// Thay vì link trực tiếp tới webhook URL, dùng Jenkins URL hiển thị trang HTML
// với nút POST tới webhook
def approvePageUrl = "${JENKINS_URL_PUBLIC}/userContent/approve.html?webhook=${approveUrl}"
```

Tạo file `$JENKINS_HOME/userContent/approve.html`:

```html
<!DOCTYPE html>
<html>
<head><title>Deployment Approval</title></head>
<body style="font-family: 'Segoe UI', Arial; text-align: center; padding: 50px;">
    <h2>🚀 Confirm Deployment Approval</h2>
    <p>Click the button below to confirm:</p>
    <script>
        const params = new URLSearchParams(window.location.search);
        const webhookUrl = params.get('webhook');
        function approve() {
            fetch(webhookUrl, { method: 'POST', body: '{}' })
                .then(() => {
                    document.getElementById('status').innerHTML = '✅ Approved! You can close this page.';
                })
                .catch(err => {
                    document.getElementById('status').innerHTML = '❌ Error: ' + err;
                });
        }
    </script>
    <button onclick="approve()" style="background:#28a745; color:white; padding:15px 40px; font-size:18px; border:none; border-radius:8px; cursor:pointer;">
        ✅ Confirm Approve
    </button>
    <p id="status"></p>
</body>
</html>
```

### Email không gửi được

```
"Authentication failed" → Kiểm tra App Password (nếu MFA)
"Connection refused"    → Port 587, TLS enabled?
"Relay access denied"   → Sender email phải thuộc domain Office 365
```

---

## Tóm tắt

| Thành phần | Cấu hình |
|---|---|
| **GitLab Webhook** | URL Jenkins + Secret Token, filter `prod` |
| **Jenkins Trigger** | GitLab Plugin → push + merge → `prod` |
| **SMTP** | `smtp.office365.com:587` + TLS |
| **Approval** | `registerWebhook()` + link trực tiếp trong email |
| **No Login** | ✅ Webhook Step Plugin — không cần tài khoản Jenkins |
| **Timeout** | Configurable (default 4 giờ) → tự động abort |
| **Notification** | Email khi approved, rejected, timeout, deployed, failed |
