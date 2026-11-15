# Autonomous AI-Driven DevSecOps Engine

## AI-Powered Secure Software Development Lifecycle and Cloud-Native Deployment Platform

---

## Project Overview

The **Autonomous AI-Driven DevSecOps Engine** is an end-to-end DevSecOps platform designed to integrate security automation, vulnerability management, software supply chain security, AI-assisted security analysis, and cloud-native application deployment into a unified CI/CD workflow.

The platform demonstrates how security can be integrated throughout the Software Development Lifecycle (SDLC), from source-code development and automated security testing to containerization, deployment, and runtime monitoring.

A sample Dummy UPI application is used to demonstrate the implementation of automated security checks and deployment workflows.

The project integrates Jenkins-based CI/CD automation with multiple security tools, including TruffleHog, SonarQube, Trivy, OWASP ZAP, DefectDojo, Syft, and Cosign.

An AI-powered security intelligence layer analyzes security scan results and generates security insights and remediation recommendations.

The application is containerized using Docker, stored in Amazon Elastic Container Registry (ECR), and deployed to Amazon Elastic Kubernetes Service (EKS). Argo CD manages Kubernetes deployments through GitOps, while Prometheus and Grafana provide monitoring and observability.

---

## Project Objectives

The primary objective is to develop an automated DevSecOps platform capable of:

- Automating application build and deployment workflows using Jenkins.
- Detecting exposed secrets through TruffleHog.
- Performing Static Application Security Testing (SAST) using SonarQube.
- Scanning application dependencies and container images using Trivy.
- Performing Dynamic Application Security Testing (DAST) using OWASP ZAP.
- Centralizing vulnerability findings using DefectDojo.
- Generating Software Bills of Materials (SBOMs) using Syft.
- Signing and verifying container images using Cosign.
- Integrating AI-assisted security analysis and remediation recommendations.
- Containerizing applications using Docker.
- Managing container images using Amazon ECR.
- Deploying applications to Amazon EKS.
- Automating Kubernetes deployments through Argo CD GitOps.
- Monitoring application metrics using Prometheus and Grafana.
- Defining application availability and HTTP error alerting rules.

---

## Project Status

**Project implementation:** Completed

The project covers automated security testing, vulnerability management, software supply chain security, AI-assisted security analysis, container image management, Kubernetes deployment, GitOps synchronization, and application monitoring.

The AWS infrastructure was used during implementation and was subsequently shut down to avoid ongoing cloud costs. Therefore, the deployment described here represents the completed implementation rather than a currently running public service.
