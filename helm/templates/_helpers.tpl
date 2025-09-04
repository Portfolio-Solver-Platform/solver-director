{{/*
Expand the name of the chart (DNS-1123 safe).
*/}}
{{- define "service.name" -}}
{{- $raw := default .Chart.Name .Values.nameOverride -}}
{{- $lower := lower $raw -}}
{{- $dashed := replace $lower "_" "-" -}}
{{- $clean := regexReplaceAll "[^a-z0-9-]+" $dashed "-" -}}
{{- $trunc := trunc 63 $clean -}}
{{- trimSuffix "-" $trunc -}}
{{- end }}

{{/*
Create a default fully qualified app name (DNS-1123 safe).
If fullnameOverride is set, sanitize it; otherwise combine Release.Name and the sanitized chart name.
*/}}
{{- define "service.fullname" -}}
{{- if .Values.fullnameOverride -}}
  {{- $raw := .Values.fullnameOverride -}}
  {{- $lower := lower $raw -}}
  {{- $dashed := replace $lower "_" "-" -}}
  {{- $clean := regexReplaceAll "[^a-z0-9-]+" $dashed "-" -}}
  {{- $trunc := trunc 63 $clean -}}
  {{- trimSuffix "-" $trunc -}}
{{- else -}}
  {{- $name := include "service.name" . -}}
  {{- if contains $name .Release.Name -}}
    {{- .Release.Name | trunc 63 | trimSuffix "-" -}}
  {{- else -}}
    {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
  {{- end -}}
{{- end -}}
{{- end }}
