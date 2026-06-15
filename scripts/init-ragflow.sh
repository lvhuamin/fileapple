#!/bin/bash
#========================================
# RAGFlow 初始化脚本
# FileApple + RAGFlow 整合项目
#========================================

set -e

# 配置
RAGFLOW_URL="${RAGFLOW_URL:-http://localhost:9380}"
API_KEY="${RAGFLOW_API_KEY:-fileapple-integration-key-2026}"
CONFIG_FILE="/root/lvhuamin/fileapple/data/ragflow-config.json"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 等待 RAGFlow 就绪
wait_for_ragflow() {
    log_info "等待 RAGFlow 服务就绪..."
    local max_attempts=60
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "${RAGFLOW_URL}/v1/system/ping" > /dev/null 2>&1; then
            log_info "RAGFlow 服务已就绪"
            return 0
        fi
        log_info "等待中... ($attempt/$max_attempts)"
        sleep 5
        attempt=$((attempt + 1))
    done

    log_error "RAGFlow 服务启动超时"
    return 1
}

# 获取认证 Token
get_auth_token() {
    log_info "获取认证 Token..."

    local response=$(curl -s -X POST "${RAGFLOW_URL}/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d '{
            "email": "admin@fileapple.local",
            "password": "fileapple-admin-2026"
        }')

    local code=$(echo $response | jq -r '.code // "1"')

    if [ "$code" != "0" ]; then
        log_warn "登录失败，尝试创建用户..."
        # 创建管理员用户
        curl -s -X POST "${RAGFLOW_URL}/v1/auth/register" \
            -H "Content-Type: application/json" \
            -d '{
                "email": "admin@fileapple.local",
                "password": "fileapple-admin-2026",
                "nickname": "FileApple Admin"
            }' > /dev/null

        # 再次尝试登录
        response=$(curl -s -X POST "${RAGFLOW_URL}/v1/auth/login" \
            -H "Content-Type: application/json" \
            -d '{
                "email": "admin@fileapple.local",
                "password": "fileapple-admin-2026"
            }')
    fi

    TOKEN=$(echo $response | jq -r '.data.access_token // empty')

    if [ -z "$TOKEN" ]; then
        log_error "无法获取 Token"
        return 1
    fi

    log_info "获取 Token 成功"
    echo $TOKEN > /tmp/ragflow_token
    echo $TOKEN
}

# 创建知识库
create_dataset() {
    local name=$1
    local desc=$2

    log_info "创建知识库: $name"

    local response=$(curl -s -X POST "${RAGFLOW_URL}/v1/datasets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${TOKEN}" \
        -d "{
            \"name\": \"$name\",
            \"description\": \"$desc\",
            \"language\": \"Chinese\",
            \"permission\": \"me\"
        }")

    local dataset_id=$(echo $response | jq -r '.data.dataset_id // empty')

    if [ -z "$dataset_id" ]; then
        log_warn "知识库 $name 可能已存在，尝试获取..."
        dataset_id=$(curl -s -X GET "${RAGFLOW_URL}/v1/datasets" \
            -H "Authorization: Bearer ${TOKEN}" \
            | jq -r ".data[] | select(.name == \"$name\") | .id // empty" | head -1)
    fi

    if [ -z "$dataset_id" ]; then
        log_error "无法创建或获取知识库: $name"
        return 1
    fi

    echo "$dataset_id"
}

# 生成 API Token
generate_api_token() {
    log_info "生成 API Token..."

    local response=$(curl -s -X POST "${RAGFLOW_URL}/v1/system/tokens" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${TOKEN}" \
        -d '{
            "name": "FileApple Integration",
            "expires_at": null
        }')

    API_TOKEN=$(echo $response | jq -r '.data.token // empty')

    if [ -z "$API_TOKEN" ]; then
        log_error "无法生成 API Token"
        return 1
    fi

    log_info "API Token 生成成功"
    echo $API_TOKEN
}

# 保存配置
save_config() {
    log_info "保存配置到 $CONFIG_FILE"

    mkdir -p $(dirname $CONFIG_FILE)

    cat > $CONFIG_FILE << EOF
{
    "ragflow_url": "${RAGFLOW_URL}",
    "api_token": "${API_TOKEN}",
    "datasets": {
        "tech-ops": "${DATASET_TECHOPS:-}",
        "psychology": "${DATASET_PSYCHOLOGY:-}",
        "relationship": "${DATASET_RELATIONSHIP:-}",
        "documents": "${DATASET_DOCUMENTS:-}",
        "audio-books": "${DATASET_AUDIOBOOKS:-}",
        "general": "${DATASET_GENERAL:-}"
    },
    "initialized_at": "$(date -Iseconds)",
    "version": "v0.25.6"
}
EOF

    log_info "配置已保存"
}

# 主流程
main() {
    echo "========================================"
    echo "  RAGFlow 初始化脚本"
    echo "========================================"

    # 等待服务就绪
    wait_for_ragflow || exit 1

    # 获取认证
    TOKEN=$(get_auth_token) || exit 1

    # 创建知识库
    DATASET_TECHOPS=$(create_dataset "技术运维" "技术运维知识库 - 服务器配置、运维脚本、DevOps")
    DATASET_PSYCHOLOGY=$(create_dataset "心理学" "心理学知识库 - 心理学理论、情绪管理")
    DATASET_RELATIONSHIP=$(create_dataset "恋爱心理" "恋爱心理知识库 - 两性关系、情感分析")
    DATASET_DOCUMENTS=$(create_dataset "文档资料" "通用文档知识库")
    DATASET_AUDIOBOOKS=$(create_dataset "有声剧" "有声剧剧本知识库")
    DATASET_GENERAL=$(create_dataset "其他" "杂项知识库")

    # 生成 API Token
    API_TOKEN=$(generate_api_token) || exit 1

    # 保存配置
    save_config

    echo ""
    echo "========================================"
    echo -e "${GREEN}  初始化完成!${NC}"
    echo "========================================"
    echo ""
    echo "RAGFlow URL: $RAGFLOW_URL"
    echo "API Token: $API_TOKEN"
    echo ""
    echo "知识库 ID:"
    echo "  技术运维: $DATASET_TECHOPS"
    echo "  心理学: $DATASET_PSYCHOLOGY"
    echo "  恋爱心理: $DATASET_RELATIONSHIP"
    echo "  文档资料: $DATASET_DOCUMENTS"
    echo "  有声剧: $DATASET_AUDIOBOOKS"
    echo "  其他: $DATASET_GENERAL"
    echo ""
    echo "配置文件: $CONFIG_FILE"
}

# 运行
main "$@"
