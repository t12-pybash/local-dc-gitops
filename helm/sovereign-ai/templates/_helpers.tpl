{{/*
Ollama service URL — used by LiteLLM and Open WebUI
*/}}
{{- define "sovereign-ai.ollamaUrl" -}}
http://ollama.{{ .Release.Namespace }}.svc.cluster.local:{{ .Values.ollama.service.port }}
{{- end }}

{{/*
LiteLLM service URL — used by Argus config
*/}}
{{- define "sovereign-ai.litellmUrl" -}}
http://litellm.{{ .Release.Namespace }}.svc.cluster.local:{{ .Values.litellm.service.port }}
{{- end }}

{{/*
Qdrant service URL — used by Argus config
*/}}
{{- define "sovereign-ai.qdrantUrl" -}}
http://qdrant.{{ .Release.Namespace }}.svc.cluster.local:6333
{{- end }}
