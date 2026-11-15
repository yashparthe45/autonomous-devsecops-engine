# Autonomous AI-Driven DevSecOps Engine

### An AI-Powered DevSecOps Platform for Automated Security Testing, Vulnerability Management, and Cloud-Native Deployment

---

## Overview

The **Autonomous AI-Driven DevSecOps Engine** is an end-to-end DevSecOps platform designed to integrate automated security testing, vulnerability management, software supply chain security, AI-assisted security analysis, and cloud-native application deployment into a unified CI/CD workflow.

The project demonstrates the implementation of security practices throughout the Software Development Lifecycle (SDLC), from source code analysis and container security testing to Kubernetes deployment and runtime monitoring.

A sample **Dummy UPI Application** is used as the target application to demonstrate the integration of security tools and automated deployment processes.

The platform uses Jenkins to orchestrate the CI/CD pipeline and integrates multiple security tools to identify potential security issues at different stages of application development.

An AI-powered security intelligence layer, integrated with Google Gemini, analyzes available security findings and generates remediation recommendations to assist in understanding and addressing vulnerabilities.

The application is containerized using Docker, with container images stored in Amazon Elastic Container Registry (ECR) and deployed on Amazon Elastic Kubernetes Service (EKS). Argo CD implements GitOps-based continuous delivery, while Prometheus and Grafana provide application monitoring and observability.

---

## Project Goals

The primary goals of this project are:

- Implement an automated DevSecOps CI/CD pipeline using Jenkins.
- Integrate security testing throughout the software development lifecycle.
- Detect exposed secrets and credentials in source code.
- Perform static and dynamic application security testing.
- Identify vulnerabilities in application dependencies and container images.
- Generate Software Bills of Materials (SBOMs).
- Implement container image signing and verification.
- Centralize security findings and vulnerability management.
- Integrate AI-assisted security analysis and remediation recommendations.
- Automate application containerization and image management.
- Deploy containerized applications to Amazon EKS.
- Implement GitOps-based continuous delivery using Argo CD.
- Configure application monitoring and observability using Prometheus and Grafana.

---

## Application Under Test

**Dummy UPI Application**

The project uses a sample UPI application as the application under test (AUT).

It provides a practical application environment for demonstrating:

- Source code security analysis.
- Dependency and container vulnerability scanning.
- Dynamic application security testing.
- Security findings management.
- Container image creation and deployment.
- Kubernetes-based application hosting.
- Application metrics collection and monitoring.

---

## Technology Stack

| Category | Technologies |
|---|---|
| Operating System | Windows, WSL2, Ubuntu |
| Source Code Management | Git, GitHub |
| CI/CD | Jenkins |
| Programming / AI Integration | Python, Google Gemini |
| Secret Scanning | TruffleHog |
| SAST | SonarQube |
| Containerization | Docker |
| Vulnerability Scanning | Trivy |
| DAST | OWASP ZAP |
| Vulnerability Management | DefectDojo |
| SBOM Generation | Syft |
| Image Signing | Cosign |
| Container Registry | Amazon ECR |
| Container Orchestration | Kubernetes, Amazon EKS |
| GitOps | Argo CD |
| Cloud Infrastructure | AWS |
| Load Balancing | AWS Application Load Balancer |
| Monitoring | Prometheus |
| Visualization | Grafana |

---
