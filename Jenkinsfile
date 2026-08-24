  pipeline {

    agent any

    options {
        disableConcurrentBuilds()
    }

    tools {
        nodejs 'NodeJS'
    }

    environment {
        SCANNER_HOME = tool 'SonarScanner'

        DEFECTDOJO_URL = 'http://host.docker.internal:8081'
        DEFECTDOJO_ENGAGEMENT_ID = '1'
    }

    stages {

        stage('Checkout Code') {
            steps {
                checkout scm
                echo 'Code checked out securely from GitHub!'
            }
        }

        stage('DevSecOps Environment Check') {
            steps {
                echo 'Verifying DevSecOps environment...'

                sh '''
                    docker --version
                    curl --version
                    node --version
                    npm --version
                    aws --version
                '''
            }
        }

        stage('AWS ECR Credential & Access Check') {
            steps {
                echo 'Verifying Jenkins AWS credentials and ECR access...'

                withCredentials([
                    [$class: 'AmazonWebServicesCredentialsBinding',
                     credentialsId: 'autonomous-devsecops-aws']
                ]) {
                    sh '''
                        set -e

                        echo "Checking AWS identity..."

                        aws sts get-caller-identity

                        echo "Checking ECR repository access..."

                        aws ecr describe-repositories \
                          --repository-names dummy-upi-app \
                          --region us-east-1

                        echo "AWS ECR access verified successfully."
                    '''
                }
            }
        }

        stage('Secrets Scanning (TruffleHog)') {
            steps {
                echo 'Hunting for leaked passwords, AWS keys, and API tokens...'

                sh '''
                    docker run --rm \
                      -v "${WORKSPACE}:/proj" \
                      trufflesecurity/trufflehog:latest \
                      filesystem /proj
                '''
            }
        }

        stage('SAST: SonarQube Code Analysis') {
            steps {
                withSonarQubeEnv('SonarQube') {

                    sh '''
                        ${SCANNER_HOME}/bin/sonar-scanner \
                          -Dsonar.projectKey=autonomous-devsecops-engine \
                          -Dsonar.projectName="Autonomous DevSecOps Engine" \
                          -Dsonar.sources=. \
                          -Dsonar.coverage.exclusions=**/*.js \
                          -Dsonar.exclusions=reports/**,screenshots/**,docker/**,docs/**,dummy-upi-app/node_modules/**
                    '''
                }
            }
        }

        stage('Quality Gate Check') {
            steps {

                timeout(time: 5, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: false
                }
            }
        }

        stage('Build Target Docker Image') {
            steps {

                echo 'Building dummy UPI application image...'

                sh '''
                    docker build -t dummy-upi-app:latest ./dummy-upi-app
                '''
            }
        }

        stage('Generate Trivy JSON Report') {
            steps {

                echo 'Generating Trivy JSON report...'

                sh '''
                    mkdir -p reports/trivy

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy image \
                      --quiet \
                      --skip-version-check \
                      --scanners vuln \
                      --format json \
                      dummy-upi-app:latest \
                      > reports/trivy/trivy-image-report.json

                    test -s reports/trivy/trivy-image-report.json

                    ls -lh reports/trivy/
                '''
            }
        }

        stage('Generate SBOM Reports with Syft') {
            steps {

                echo 'Generating CycloneDX and SPDX SBOM reports...'

                sh '''
                    mkdir -p reports/sbom

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      anchore/syft:latest \
                      dummy-upi-app:latest \
                      -o cyclonedx-json \
                      > reports/sbom/dummy-upi-app-cyclonedx.json

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      anchore/syft:latest \
                      dummy-upi-app:latest \
                      -o spdx-json \
                      > reports/sbom/dummy-upi-app-spdx.json

                    test -s reports/sbom/dummy-upi-app-cyclonedx.json
                    test -s reports/sbom/dummy-upi-app-spdx.json

                    echo "SBOM generation completed successfully."
                '''
            }
        }

        stage('Sign and Verify Image Artifact with Cosign') {
            steps {

                echo 'Signing and verifying Docker image artifact...'

                withCredentials([
                    file(credentialsId: 'cosign-private-key', variable: 'COSIGN_PRIVATE_KEY'),
                    file(credentialsId: 'cosign-public-key', variable: 'COSIGN_PUBLIC_KEY'),
                    string(credentialsId: 'cosign-key-password', variable: 'COSIGN_PASSWORD')
                ]) {

                    sh '''
                        set -e

                        mkdir -p reports/cosign
                        mkdir -p .jenkins-tools

                        if [ ! -x .jenkins-tools/cosign ]; then

                            curl -sSL -o .jenkins-tools/cosign \
                              https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64

                            chmod +x .jenkins-tools/cosign
                        fi

                        .jenkins-tools/cosign version

                        COSIGN_TEMP_DIR="$(mktemp -d)"

                        trap 'rm -rf "${COSIGN_TEMP_DIR}"' EXIT

                        install -m 600 "${COSIGN_PRIVATE_KEY}" \
                          "${COSIGN_TEMP_DIR}/cosign.key"

                        install -m 644 "${COSIGN_PUBLIC_KEY}" \
                          "${COSIGN_TEMP_DIR}/cosign.pub"

                        docker save dummy-upi-app:latest \
                          -o reports/cosign/dummy-upi-app-image.tar

                        sha256sum reports/cosign/dummy-upi-app-image.tar \
                          | tee reports/cosign/dummy-upi-app-image.sha256

                        .jenkins-tools/cosign sign-blob \
                          --yes \
                          --key "${COSIGN_TEMP_DIR}/cosign.key" \
                          --bundle reports/cosign/dummy-upi-app-image.sigstore.json \
                          reports/cosign/dummy-upi-app-image.tar

                        test -s reports/cosign/dummy-upi-app-image.sigstore.json

                        set +e

                        .jenkins-tools/cosign verify-blob \
                          --key "${COSIGN_TEMP_DIR}/cosign.pub" \
                          --bundle reports/cosign/dummy-upi-app-image.sigstore.json \
                          reports/cosign/dummy-upi-app-image.tar \
                          > reports/cosign/cosign-verify-raw-output.txt 2>&1

                        VERIFY_EXIT_CODE=$?

                        set -e

                        cat reports/cosign/cosign-verify-raw-output.txt

                        if [ "${VERIFY_EXIT_CODE}" -eq 0 ]; then

                            echo "Cosign Signature Verification: PASSED" \
                              > reports/cosign/dummy-upi-app-signature-verification.txt

                        else

                            echo "Cosign Signature Verification: FAILED" \
                              > reports/cosign/dummy-upi-app-signature-verification.txt

                            exit "${VERIFY_EXIT_CODE}"

                        fi

                        rm -f reports/cosign/dummy-upi-app-image.tar

                        echo "Cosign signing and verification completed."
                    '''
                }
            }
        }

        stage('DAST: OWASP ZAP Dynamic Scan') {
            steps {

                echo 'Running OWASP ZAP dynamic security testing...'

                sh '''
                    DAST_NETWORK="devsecops-net-${BUILD_NUMBER}"
                    APP_CONTAINER="dummy-app-${BUILD_NUMBER}"
                    ZAP_CONTAINER="zap-scanner-${BUILD_NUMBER}"
                    ZAP_VOLUME="zap-reports-${BUILD_NUMBER}"

                    mkdir -p reports/zap

                    docker rm -f "${APP_CONTAINER}" "${ZAP_CONTAINER}" 2>/dev/null || true
                    docker network rm "${DAST_NETWORK}" 2>/dev/null || true
                    docker volume rm "${ZAP_VOLUME}" 2>/dev/null || true

                    docker network create "${DAST_NETWORK}"
                    docker volume create "${ZAP_VOLUME}"

                    docker run -d \
                      --name "${APP_CONTAINER}" \
                      --network "${DAST_NETWORK}" \
                      dummy-upi-app:latest

                    sleep 10

                    docker run \
                      --name "${ZAP_CONTAINER}" \
                      -u root \
                      --network "${DAST_NETWORK}" \
                      -v "${ZAP_VOLUME}:/zap/wrk" \
                      ghcr.io/zaproxy/zaproxy:stable \
                      zap-baseline.py \
                      -t "http://${APP_CONTAINER}:3000" \
                      -r zap-report.html \
                      -x zap-report.xml \
                      -I || true

                    docker cp \
                      "${ZAP_CONTAINER}:/zap/wrk/zap-report.html" \
                      reports/zap/zap-report.html

                    docker cp \
                      "${ZAP_CONTAINER}:/zap/wrk/zap-report.xml" \
                      reports/zap/zap-report.xml

                    test -s reports/zap/zap-report.html
                    test -s reports/zap/zap-report.xml

                    echo "OWASP ZAP scan completed."
                '''
            }
        }

        stage('Upload Trivy Report to DefectDojo') {
            steps {

                echo 'Uploading Trivy report to DefectDojo...'

                withCredentials([
                    string(
                        credentialsId: 'defectdojo-api-token',
                        variable: 'DEFECTDOJO_API_TOKEN'
                    )
                ]) {

                    sh '''
                        test -s reports/trivy/trivy-image-report.json

                        set +x

                        HTTP_CODE=$(curl -sS \
                          -o reports/trivy/defectdojo-trivy-upload-response.json \
                          -w "%{http_code}" \
                          -X POST "${DEFECTDOJO_URL}/api/v2/import-scan/" \
                          -H "Authorization: Token ${DEFECTDOJO_API_TOKEN}" \
                          -F "engagement=${DEFECTDOJO_ENGAGEMENT_ID}" \
                          -F "scan_type=Trivy Scan" \
                          -F "file=@reports/trivy/trivy-image-report.json" \
                          -F "minimum_severity=Info" \
                          -F "active=true" \
                          -F "verified=false" \
                          -F "close_old_findings=false" \
                          -F "push_to_jira=false")

                        set -x

                        echo "DefectDojo HTTP status: ${HTTP_CODE}"

                        if [ "${HTTP_CODE}" -lt 200 ] || [ "${HTTP_CODE}" -ge 300 ]; then
                            exit 1
                        fi
                    '''
                }
            }
        }

        stage('Upload ZAP Report to DefectDojo') {
            steps {

                echo 'Uploading ZAP report to DefectDojo...'

                withCredentials([
                    string(
                        credentialsId: 'defectdojo-api-token',
                        variable: 'DEFECTDOJO_API_TOKEN'
                    )
                ]) {

                    sh '''
                        test -s reports/zap/zap-report.xml

                        set +x

                        HTTP_CODE=$(curl -sS \
                          -o reports/zap/defectdojo-zap-upload-response.json \
                          -w "%{http_code}" \
                          -X POST "${DEFECTDOJO_URL}/api/v2/import-scan/" \
                          -H "Authorization: Token ${DEFECTDOJO_API_TOKEN}" \
                          -F "engagement=${DEFECTDOJO_ENGAGEMENT_ID}" \
                          -F "scan_type=ZAP Scan" \
                          -F "file=@reports/zap/zap-report.xml" \
                          -F "minimum_severity=Info" \
                          -F "active=true" \
                          -F "verified=false" \
                          -F "close_old_findings=false" \
                          -F "push_to_jira=false")

                        set -x

                        echo "DefectDojo HTTP status: ${HTTP_CODE}"

                        if [ "${HTTP_CODE}" -lt 200 ] || [ "${HTTP_CODE}" -ge 300 ]; then
                            exit 1
                        fi
                    '''
                }
            }
        }

        stage('AI Security Intelligence Analysis') {
            steps {

                echo 'Running AI Security Intelligence analysis...'

                sh '''
                    set -e

                    mkdir -p ai-security-engine/input
                    mkdir -p ai-security-engine/output
                    mkdir -p reports/ai

                    rm -f ai-security-engine/input/* || true
                    rm -f ai-security-engine/output/* || true
                    rm -f reports/ai/* || true

                    cp reports/trivy/trivy-image-report.json \
                       ai-security-engine/input/trivy-image-report.json

                    cp reports/zap/zap-report.xml \
                       ai-security-engine/input/zap-report.xml

                    cp reports/sbom/dummy-upi-app-cyclonedx.json \
                       ai-security-engine/input/dummy-upi-app-cyclonedx.json

                    cp reports/cosign/dummy-upi-app-signature-verification.txt \
                       ai-security-engine/input/cosign-verification.txt

                    docker run --rm \
                      -v jenkins_home:/var/jenkins_home \
                      -w "$WORKSPACE" \
                      python:3.12-slim \
                      python ai-security-engine/src/security_intelligence.py

                    cp ai-security-engine/output/ai-security-summary.json \
                       reports/ai/ai-security-summary.json

                    cp ai-security-engine/output/ai-security-report.md \
                       reports/ai/ai-security-report.md

                    cp ai-security-engine/output/release-decision.txt \
                       reports/ai/release-decision.txt

                    cat reports/ai/release-decision.txt

                    test -s reports/ai/ai-security-summary.json
                    test -s reports/ai/ai-security-report.md
                    test -s reports/ai/release-decision.txt
                '''
            }
        }

        stage('AI Remediation Analysis') {
            steps {

                echo 'Running AI security remediation analysis...'

                withCredentials([
                    string(
                        credentialsId: 'gemini-api-key',
                        variable: 'GEMINI_API_KEY'
                    )
                ]) {

                    sh '''
                        set -e

                        mkdir -p ai-security-engine/input
                        mkdir -p ai-security-engine/output
                        mkdir -p reports/ai

                        cp reports/trivy/trivy-image-report.json \
                           ai-security-engine/input/trivy-image-report.json

                        cp reports/zap/zap-report.xml \
                           ai-security-engine/input/zap-report.xml

                        cp reports/sbom/dummy-upi-app-cyclonedx.json \
                           ai-security-engine/input/dummy-upi-app-cyclonedx.json

                        cp reports/cosign/dummy-upi-app-signature-verification.txt \
                           ai-security-engine/input/cosign-verification.txt

                        docker run --rm \
                          -v jenkins_home:/var/jenkins_home \
                          -w "$WORKSPACE" \
                          -e GEMINI_API_KEY="$GEMINI_API_KEY" \
                          python:3.12-slim \
                          sh -c 'pip install --no-cache-dir google-genai && python ai-security-engine/src/ai_remediation.py'

                        cp ai-security-engine/output/ai-remediation.json \
                           reports/ai/ai-remediation.json

                        cp ai-security-engine/output/ai-remediation.md \
                           reports/ai/ai-remediation.md

                        test -s reports/ai/ai-remediation.json
                        test -s reports/ai/ai-remediation.md
                    '''
                }
            }
        }

        /*
         * ============================================================
         * SECURITY REPORTING GATE
         * ============================================================
         *
         * Trivy still reports CRITICAL vulnerabilities.
         * For this integration test we DO NOT block the ECR/GitOps flow.
         *
         * The intentionally vulnerable Dummy UPI app is being used
         * to demonstrate the security findings.
         */

        stage('SCA: Trivy Container Scan Critical Gate') {
            steps {

                echo 'Running Trivy CRITICAL scan for security reporting...'

                sh '''
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy image \
                      --severity CRITICAL \
                      dummy-upi-app:latest || true

                    echo "Trivy CRITICAL findings reported."
                    echo "Integration test continues to CD stages."
                '''
            }
        }

        /*
         * ============================================================
         * CD - AMAZON ECR
         * ============================================================
         */

        stage('Push Docker Image to Amazon ECR') {
            steps {

                echo 'Pushing Docker image to Amazon ECR...'

                withCredentials([
                    [$class: 'AmazonWebServicesCredentialsBinding',
                     credentialsId: 'autonomous-devsecops-aws']
                ]) {

                    sh '''
                        set -e

                        AWS_REGION="us-east-1"
                        ECR_REGISTRY="285364193286.dkr.ecr.us-east-1.amazonaws.com"
                        ECR_REPOSITORY="dummy-upi-app"
                        IMAGE_TAG="${BUILD_NUMBER}"

                        echo "Logging in to Amazon ECR..."

                        aws ecr get-login-password \
                          --region "${AWS_REGION}" | \
                        docker login \
                          --username AWS \
                          --password-stdin "${ECR_REGISTRY}"

                        echo "Tagging image..."

                        docker tag \
                          dummy-upi-app:latest \
                          "${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

                        echo "Pushing image..."

                        docker push \
                          "${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

                        echo "============================================"
                        echo "ECR PUSH SUCCESSFUL"
                        echo "============================================"

                        echo "Image:"
                        echo "${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"
                    '''
                }
            }
        }

        /*
         * ============================================================
         * CD - GITOPS / ARGO CD
         * ============================================================
         */

        stage('Update Kubernetes Manifest for GitOps') {
            steps {

                echo 'Updating Kubernetes manifest with the new ECR image...'

                withCredentials([
                    usernamePassword(
                        credentialsId: 'github-credentials',
                        usernameVariable: 'GIT_USERNAME',
                        passwordVariable: 'GIT_TOKEN'
                    )
                ]) {

                    sh '''
                        set -e

                        ECR_REGISTRY="285364193286.dkr.ecr.us-east-1.amazonaws.com"
                        ECR_REPOSITORY="dummy-upi-app"
                        IMAGE_TAG="${BUILD_NUMBER}"

                        IMAGE="${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

                        echo "New deployment image:"
                        echo "${IMAGE}"

                        echo "Current Kubernetes image:"
                        grep "image:" k8s/base/deployment.yaml

                        echo "Updating deployment.yaml..."

                        sed -i \
                          "s|image: .*dummy-upi-app:.*|image: ${IMAGE}|" \
                          k8s/base/deployment.yaml

                        echo "Updated Kubernetes image:"
                        grep "image:" k8s/base/deployment.yaml

                        git config user.name "Jenkins CI"
                        git config user.email "jenkins@autonomous-devsecops.local"

                        git add k8s/base/deployment.yaml

                        echo "Git diff:"
                        git diff --cached

                        git commit \
                          -m "Update dummy-upi-app image to ${IMAGE_TAG}" || {

                            echo "No manifest changes detected."

                            exit 0
                        }

                        echo "Pushing Kubernetes manifest to cloud-deployment..."

                        git push \
                          https://${GIT_USERNAME}:${GIT_TOKEN}@github.com/yashparthe45/autonomous-devsecops-engine.git \
                          HEAD:refs/heads/main

                        echo "============================================"
                        echo "GITOPS UPDATE SUCCESSFUL"
                        echo "============================================"

                        echo "Argo CD should now detect the change."
                    '''
                }
            }
        }
    }

    post {

        always {

            echo 'Cleaning temporary DAST resources and archiving reports...'

            sh '''
                DAST_NETWORK="devsecops-net-${BUILD_NUMBER}"
                APP_CONTAINER="dummy-app-${BUILD_NUMBER}"
                ZAP_CONTAINER="zap-scanner-${BUILD_NUMBER}"
                ZAP_VOLUME="zap-reports-${BUILD_NUMBER}"

                docker rm -f "${APP_CONTAINER}" "${ZAP_CONTAINER}" 2>/dev/null || true

                docker network rm "${DAST_NETWORK}" 2>/dev/null || true

                docker volume rm "${ZAP_VOLUME}" 2>/dev/null || true

                rm -f reports/cosign/dummy-upi-app-image.tar 2>/dev/null || true
            '''

            archiveArtifacts \
                artifacts: 'reports/**/*.json,reports/**/*.xml,reports/**/*.html,reports/**/*.txt,reports/**/*.sha256,reports/**/*.md', \
                fingerprint: true, \
                allowEmptyArchive: true
        }

        success {

            echo '''
            ============================================
            PIPELINE COMPLETED SUCCESSFULLY
            ============================================

            CI:
            - GitHub
            - Jenkins
            - TruffleHog
            - SonarQube
            - Trivy
            - OWASP ZAP
            - DefectDojo
            - Syft
            - Cosign
            - AI Security Analysis

            CD:
            - Docker image pushed to Amazon ECR
            - Kubernetes manifest updated
            - GitOps commit pushed to cloud-deployment
            - Argo CD will synchronize the change to EKS

            ============================================
            '''
        }

        failure {

            echo '''
            ============================================
            PIPELINE FAILED
            ============================================

            Check Jenkins logs for:
            - Security stage failure
            - Docker build failure
            - ECR authentication/push failure
            - GitHub authentication failure
            - GitOps manifest update failure

            ============================================
            '''
        }
    }
}
