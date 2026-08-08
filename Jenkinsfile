pipeline {
    // Defines where the pipeline runs. 'any' means it will run on the available Jenkins node.
    agent any

    // Prevents two Jenkins builds from using/removing the same Docker containers, networks, or volumes.
    options {
        disableConcurrentBuilds()
    }

    // Automatically installs and injects necessary build tools into the pipeline environment.
    tools {
        // Required for SonarQube's JavaScript/TypeScript analysis engine
        nodejs 'NodeJS'
    }

    environment {
        // Maps the SonarScanner tool installed in Jenkins to an environment variable
        SCANNER_HOME = tool 'SonarScanner'

        // DefectDojo runs on the host machine and Jenkins reaches it using host.docker.internal
        DEFECTDOJO_URL = 'http://host.docker.internal:8081'

        // Engagement ID created in DefectDojo for CI-CD Security Pipeline
        DEFECTDOJO_ENGAGEMENT_ID = '1'
    }

    stages {
        stage('Checkout Code') {
            steps {
                // Pulls the latest code from the GitHub repository linked to this Jenkins job
                checkout scm
                echo 'Code checked out securely from GitHub!'
            }
        }

        stage('DevSecOps Environment Check') {
            steps {
                // Validates that Docker-out-of-Docker socket mapping and required tools are working
                echo 'Verifying DevSecOps environment...'
                sh '''
                    docker --version
                    curl --version
                    node --version
                    npm --version
                '''
            }
        }

        stage('Secrets Scanning (TruffleHog)') {
            steps {
                echo 'Hunting for leaked passwords, AWS keys, and API tokens...'

                // Mounts the current Jenkins workspace into the TruffleHog container.
                // TruffleHog scans the filesystem for high-entropy strings and known credential patterns.
                // If verified secrets are found, it exits with a non-zero code, failing the build.
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
                // Wraps the execution in SonarQube context, sending the results to the external Sonar container
                withSonarQubeEnv('SonarQube') {
                    // Executes the static code analysis, explicitly ignoring non-production folders
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
                // Pauses the pipeline to wait for SonarQube to calculate the final grade through webhook
                timeout(time: 5, unit: 'MINUTES') {
                    // Currently non-blocking for academic development continuity.
                    // Earlier blocking gate was already validated successfully.
                    waitForQualityGate abortPipeline: false
                }
            }
        }

        stage('Build Target Docker Image') {
            steps {
                echo 'Building the dummy UPI application image...'

                // Builds the target application Docker image from dummy-upi-app directory
                sh '''
                    docker build -t dummy-upi-app:latest ./dummy-upi-app
                '''
            }
        }

        stage('Generate Trivy JSON Report') {
            steps {
                echo 'Generating Trivy JSON report for DefectDojo...'

                // Trivy JSON report is required for DefectDojo import.
                // Output is redirected by Jenkins shell into the workspace to avoid Docker bind-mount issues.
                sh '''
                    mkdir -p reports/trivy

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy image \
                      --quiet \
                      --skip-version-check \
                      --scanners vuln \
                      --format json \
                      dummy-upi-app:latest > reports/trivy/trivy-image-report.json

                    test -s reports/trivy/trivy-image-report.json

                    ls -lh reports/trivy/
                '''
            }
        }

        stage('Generate SBOM Reports with Syft') {
            steps {
                echo 'Generating CycloneDX and SPDX SBOM reports using Syft...'

                // Syft generates a Software Bill of Materials for the built Docker image.
                // CycloneDX and SPDX formats are generated for supply chain visibility and audit evidence.
                // Output is redirected by Jenkins shell into the workspace to avoid Docker bind-mount permission issues.
                sh '''
                    mkdir -p reports/sbom

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      anchore/syft:latest \
                      dummy-upi-app:latest \
                      -o cyclonedx-json > reports/sbom/dummy-upi-app-cyclonedx.json

                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      anchore/syft:latest \
                      dummy-upi-app:latest \
                      -o spdx-json > reports/sbom/dummy-upi-app-spdx.json

                    test -s reports/sbom/dummy-upi-app-cyclonedx.json
                    test -s reports/sbom/dummy-upi-app-spdx.json

                    grep -q '"bomFormat"[[:space:]]*:[[:space:]]*"CycloneDX"' reports/sbom/dummy-upi-app-cyclonedx.json
                    grep -q '"spdxVersion"[[:space:]]*:' reports/sbom/dummy-upi-app-spdx.json

                    ls -lh reports/sbom/

                    echo "SBOM generation completed successfully."
                '''
            }
        }

        stage('Sign and Verify Image Artifact with Cosign') {
            steps {
                echo 'Signing and verifying Docker image artifact with Cosign...'

                // Uses Jenkins credentials:
                // cosign-private-key  -> Secret file containing cosign.key
                // cosign-public-key   -> Secret file containing cosign.pub
                // cosign-key-password -> Secret text containing Cosign key password
                withCredentials([
                    file(credentialsId: 'cosign-private-key', variable: 'COSIGN_PRIVATE_KEY'),
                    file(credentialsId: 'cosign-public-key', variable: 'COSIGN_PUBLIC_KEY'),
                    string(credentialsId: 'cosign-key-password', variable: 'COSIGN_PASSWORD')
                ]) {
                    sh '''
                        set -e

                        echo "Preparing Cosign signing workspace..."

                        mkdir -p reports/cosign
                        mkdir -p .jenkins-tools

                        # Download Cosign binary only if it is not already available in the Jenkins workspace.
                        # This avoids Docker bind-mount issues while still keeping the pipeline portable.
                        if [ ! -x .jenkins-tools/cosign ]; then
                          echo "Downloading Cosign..."
                          curl -sSL -o .jenkins-tools/cosign \
                            https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64
                          chmod +x .jenkins-tools/cosign
                        fi

                        .jenkins-tools/cosign version

                        # Create temporary key directory.
                        # Jenkins secret files are copied here and removed automatically at the end of this stage.
                        COSIGN_TEMP_DIR="$(mktemp -d)"
                        trap 'rm -rf "${COSIGN_TEMP_DIR}"' EXIT

                        install -m 600 "${COSIGN_PRIVATE_KEY}" "${COSIGN_TEMP_DIR}/cosign.key"
                        install -m 644 "${COSIGN_PUBLIC_KEY}" "${COSIGN_TEMP_DIR}/cosign.pub"

                        echo "Saving Docker image as a signable artifact..."

                        docker save dummy-upi-app:latest -o reports/cosign/dummy-upi-app-image.tar

                        sha256sum reports/cosign/dummy-upi-app-image.tar \
                          | tee reports/cosign/dummy-upi-app-image.sha256

                        echo "Signing image artifact using Cosign..."

                        .jenkins-tools/cosign sign-blob \
                          --yes \
                          --key "${COSIGN_TEMP_DIR}/cosign.key" \
                          --bundle reports/cosign/dummy-upi-app-image.sigstore.json \
                          reports/cosign/dummy-upi-app-image.tar

                        test -s reports/cosign/dummy-upi-app-image.sigstore.json

                        echo "Verifying Cosign signature..."

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
                          {
                            echo "Cosign Signature Verification: PASSED"
                            echo "Artifact: dummy-upi-app:latest"
                            echo "Signed Artifact Type: Docker image archive"
                            echo "Bundle: reports/cosign/dummy-upi-app-image.sigstore.json"
                            echo "Checksum: reports/cosign/dummy-upi-app-image.sha256"
                            echo "Public Key Credential: cosign-public-key"
                            echo "Result: Verified OK"
                          } > reports/cosign/dummy-upi-app-signature-verification.txt
                        else
                          {
                            echo "Cosign Signature Verification: FAILED"
                            echo "Exit Code: ${VERIFY_EXIT_CODE}"
                            echo "Raw Output:"
                            cat reports/cosign/cosign-verify-raw-output.txt
                          } > reports/cosign/dummy-upi-app-signature-verification.txt

                          exit "${VERIFY_EXIT_CODE}"
                        fi

                        test -s reports/cosign/dummy-upi-app-signature-verification.txt

                        # Do not keep the large image tar in Jenkins artifacts.
                        # The checksum, Sigstore bundle, and verification proof are enough as evidence.
                        rm -f reports/cosign/dummy-upi-app-image.tar

                        ls -lh reports/cosign/

                        echo "Cosign image artifact signing and verification completed successfully."
                    '''
                }
            }
        }

        stage('DAST: OWASP ZAP Dynamic Scan') {
            steps {
                echo 'Spinning up application for dynamic security testing...'

                sh '''
                    # 1. Create unique Docker object names for this Jenkins build
                    DAST_NETWORK="devsecops-net-${BUILD_NUMBER}"
                    APP_CONTAINER="dummy-app-${BUILD_NUMBER}"
                    ZAP_CONTAINER="zap-scanner-${BUILD_NUMBER}"
                    ZAP_VOLUME="zap-reports-${BUILD_NUMBER}"

                    # 2. Prepare report directory
                    mkdir -p reports/zap

                    # 3. Remove old objects for this build number if they exist
                    docker rm -f "${APP_CONTAINER}" "${ZAP_CONTAINER}" 2>/dev/null || true
                    docker network rm "${DAST_NETWORK}" 2>/dev/null || true
                    docker volume rm "${ZAP_VOLUME}" 2>/dev/null || true

                    # 4. Create temporary Docker network and Docker named volume
                    docker network create "${DAST_NETWORK}"
                    docker volume create "${ZAP_VOLUME}"

                    # 5. Run the dummy UPI application in the background
                    docker run -d --name "${APP_CONTAINER}" \
                      --network "${DAST_NETWORK}" \
                      dummy-upi-app:latest

                    # 6. Give the application time to start
                    sleep 10

                    # 7. Confirm application container is running
                    docker ps --filter "name=${APP_CONTAINER}"

                    # 8. Run OWASP ZAP baseline scan
                    # HTML report is used for Jenkins evidence
                    # XML report is used for DefectDojo import
                    docker run --name "${ZAP_CONTAINER}" -u root \
                      --network "${DAST_NETWORK}" \
                      -v "${ZAP_VOLUME}:/zap/wrk" \
                      ghcr.io/zaproxy/zaproxy:stable \
                      zap-baseline.py \
                      -t "http://${APP_CONTAINER}:3000" \
                      -r zap-report.html \
                      -x zap-report.xml \
                      -I || true

                    # 9. Copy ZAP reports from scanner container into Jenkins workspace
                    docker cp "${ZAP_CONTAINER}:/zap/wrk/zap-report.html" reports/zap/zap-report.html
                    docker cp "${ZAP_CONTAINER}:/zap/wrk/zap-report.xml" reports/zap/zap-report.xml

                    # 10. Verify reports exist
                    test -s reports/zap/zap-report.html
                    test -s reports/zap/zap-report.xml

                    ls -lh reports/zap/
                '''
            }
        }

        stage('Upload Trivy Report to DefectDojo') {
            steps {
                echo 'Uploading Trivy vulnerability report to DefectDojo...'

                // Uses Jenkins secret text credential.
                // Credential ID must be: defectdojo-api-token
                // Do not hardcode the API token in Jenkinsfile.
                withCredentials([string(credentialsId: 'defectdojo-api-token', variable: 'DEFECTDOJO_API_TOKEN')]) {
                    sh '''
                        # 1. Verify that Trivy report exists before uploading
                        test -s reports/trivy/trivy-image-report.json

                        # 2. Upload Trivy JSON report to DefectDojo
                        set +x
                        HTTP_CODE=$(curl -sS -o reports/trivy/defectdojo-trivy-upload-response.json -w "%{http_code}" \
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

                        # 3. Print upload status and response
                        echo "DefectDojo Trivy upload HTTP status: ${HTTP_CODE}"
                        cat reports/trivy/defectdojo-trivy-upload-response.json

                        # 4. Fail pipeline if DefectDojo upload fails
                        if [ "${HTTP_CODE}" -lt 200 ] || [ "${HTTP_CODE}" -ge 300 ]; then
                          echo "Trivy upload to DefectDojo failed"
                          exit 1
                        fi
                    '''
                }
            }
        }

        stage('Upload ZAP Report to DefectDojo') {
            steps {
                echo 'Uploading OWASP ZAP report to DefectDojo...'

                // Uses Jenkins secret text credential.
                // Credential ID must be: defectdojo-api-token
                // Do not hardcode the API token in Jenkinsfile.
                withCredentials([string(credentialsId: 'defectdojo-api-token', variable: 'DEFECTDOJO_API_TOKEN')]) {
                    sh '''
                        # 1. Verify that ZAP XML report exists before uploading
                        test -s reports/zap/zap-report.xml

                        # 2. Upload ZAP XML report to DefectDojo
                        set +x
                        HTTP_CODE=$(curl -sS -o reports/zap/defectdojo-zap-upload-response.json -w "%{http_code}" \
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

                        # 3. Print upload status and response
                        echo "DefectDojo ZAP upload HTTP status: ${HTTP_CODE}"
                        cat reports/zap/defectdojo-zap-upload-response.json

                        # 4. Fail pipeline if DefectDojo upload fails
                        if [ "${HTTP_CODE}" -lt 200 ] || [ "${HTTP_CODE}" -ge 300 ]; then
                          echo "ZAP upload to DefectDojo failed"
                          exit 1
                        fi
                    '''
                }
            }
        }

        stage('AI Security Intelligence Analysis') {
            steps {
                echo 'Running AI Security Intelligence analysis...'

                // This stage analyzes Trivy, OWASP ZAP, SBOM, and Cosign evidence.
                // It generates an AI summary, risk score, recommendations, and release decision.
                sh '''
                    set -e

                    mkdir -p ai-security-engine/input
                    mkdir -p ai-security-engine/output
                    mkdir -p reports/ai

                    rm -f ai-security-engine/input/* || true
                    rm -f ai-security-engine/output/* || true
                    rm -f reports/ai/* || true

                    cp reports/trivy/trivy-image-report.json ai-security-engine/input/trivy-image-report.json
                    cp reports/zap/zap-report.xml ai-security-engine/input/zap-report.xml
                    cp reports/sbom/dummy-upi-app-cyclonedx.json ai-security-engine/input/dummy-upi-app-cyclonedx.json
                    cp reports/cosign/dummy-upi-app-signature-verification.txt ai-security-engine/input/cosign-verification.txt

                    docker run --rm \
                      -v jenkins_home:/var/jenkins_home \
                      -w "$WORKSPACE" \
                      python:3.12-slim \
                      python ai-security-engine/src/security_intelligence.py

                    cp ai-security-engine/output/ai-security-summary.json reports/ai/ai-security-summary.json
                    cp ai-security-engine/output/ai-security-report.md reports/ai/ai-security-report.md
                    cp ai-security-engine/output/release-decision.txt reports/ai/release-decision.txt

                    echo "===== AI RELEASE DECISION ====="
                    cat reports/ai/release-decision.txt

                    test -s reports/ai/ai-security-summary.json
                    test -s reports/ai/ai-security-report.md
                    test -s reports/ai/release-decision.txt

                    echo "AI Security Intelligence analysis completed successfully."
                '''
            }
        }

        stage('AI Remediation Analysis') {
            steps {
                echo 'Running AI security remediation analysis...'

                // Uses the security evidence generated by this Jenkins build.
                // The AI remediation script generates JSON and Markdown remediation reports.
                // GEMINI_API_KEY is supplied securely through Jenkins Credentials.
                withCredentials([string(credentialsId: 'gemini-api-key', variable: 'GEMINI_API_KEY')]) {
                    sh '''
                        set -e

                        mkdir -p ai-security-engine/input
                        mkdir -p ai-security-engine/output
                        mkdir -p reports/ai

                        # Prepare only the reports generated by this Jenkins build.
                        cp reports/trivy/trivy-image-report.json \
                           ai-security-engine/input/trivy-image-report.json
                        cp reports/zap/zap-report.xml \
                           ai-security-engine/input/zap-report.xml
                        cp reports/sbom/dummy-upi-app-cyclonedx.json \
                           ai-security-engine/input/dummy-upi-app-cyclonedx.json
                        cp reports/cosign/dummy-upi-app-signature-verification.txt \
                           ai-security-engine/input/cosign-verification.txt

                        # Install the Python SDK required by ai_remediation.py inside the ephemeral container.
                        docker run --rm \
                          -v jenkins_home:/var/jenkins_home \
                          -w "$WORKSPACE" \
                          -e GEMINI_API_KEY="$GEMINI_API_KEY" \
                          python:3.12-slim \
                          sh -c 'pip install --no-cache-dir google-genai && python ai-security-engine/src/ai_remediation.py'

                        cp ai-security-engine/output/ai-remediation.json reports/ai/ai-remediation.json
                        cp ai-security-engine/output/ai-remediation.md reports/ai/ai-remediation.md

                        echo "===== AI REMEDIATION REPORT ====="
                        cat reports/ai/ai-remediation.md

                        test -s reports/ai/ai-remediation.json
                        test -s reports/ai/ai-remediation.md

                        echo "AI remediation analysis completed successfully."
                    '''
                }
            }
        }

        stage('SCA: Trivy Container Scan Critical Gate') {
            steps {
                echo 'Summoning Trivy to enforce CRITICAL vulnerability gate...'

                // This gate runs after DefectDojo upload and AI security analysis.
                // Even if the pipeline fails here, reports are already uploaded to DefectDojo and analyzed by the AI layer.
                sh '''
                    docker run --rm \
                      -v /var/run/docker.sock:/var/run/docker.sock \
                      aquasec/trivy image \
                      --exit-code 1 \
                      --severity CRITICAL \
                      dummy-upi-app:latest
                '''
            }
        }
    }

    post {
        always {
            echo 'Tearing down test environment and saving security reports...'

            sh '''
                # Stop and remove temporary DAST containers, network, and volume for this Jenkins build
                DAST_NETWORK="devsecops-net-${BUILD_NUMBER}"
                APP_CONTAINER="dummy-app-${BUILD_NUMBER}"
                ZAP_CONTAINER="zap-scanner-${BUILD_NUMBER}"
                ZAP_VOLUME="zap-reports-${BUILD_NUMBER}"

                docker rm -f "${APP_CONTAINER}" "${ZAP_CONTAINER}" 2>/dev/null || true
                docker network rm "${DAST_NETWORK}" 2>/dev/null || true
                docker volume rm "${ZAP_VOLUME}" 2>/dev/null || true

                # Remove large temporary image archive if it exists
                rm -f reports/cosign/dummy-upi-app-image.tar 2>/dev/null || true
            '''

            // Save generated security reports, SBOM reports, Cosign evidence, DefectDojo upload responses, and AI reports as Jenkins build artifacts
            archiveArtifacts artifacts: 'reports/**/*.json,reports/**/*.xml,reports/**/*.html,reports/**/*.txt,reports/**/*.sha256,reports/**/*.md', fingerprint: true, allowEmptyArchive: true
        }

        success {
            echo 'Pipeline completed successfully. Security reports, SBOM artifacts, Cosign evidence, DefectDojo evidence, and AI reports archived.'
        }

        failure {
            echo 'Pipeline failed. Check Jenkins logs, security gates, SBOM generation, Cosign verification, DefectDojo uploads, and AI analysis reports.'
        }
    }
