package types

import "time"

// TriageReport is the single central output model for all triage commands.
// Every fetcher populates a section; every renderer reads from this struct.
type TriageReport struct {
	Target          TargetRef             `json:"target"`
	Workload        WorkloadSummary       `json:"workload"`
	Images          []ImageSummary        `json:"images"`
	Security        SecuritySummary       `json:"security"`
	ServiceAccount  ServiceAccountSummary `json:"serviceAccount"`
	Ownership       OwnerChain            `json:"ownership"`
	RecentEvents    []EventSummary        `json:"recentEvents"`
	Logs            LogSnippet            `json:"logs"`
	Network         NetworkSummary        `json:"network"`
	RBAC            RBACSummary           `json:"rbac"`
	SummaryBullets  []string              `json:"summaryBullets,omitempty"`
	Recommendations []string              `json:"recommendations"`
	TriageReadout   string                `json:"triageReadout,omitempty"`
	GeneratedAt     time.Time             `json:"generatedAt"`
}

// TargetRef identifies what was triaged.
type TargetRef struct {
	Kind      string `json:"kind"`
	Name      string `json:"name"`
	Namespace string `json:"namespace"`
}

// WorkloadSummary holds basic workload metadata.
type WorkloadSummary struct {
	Name         string            `json:"name"`
	Namespace    string            `json:"namespace"`
	Kind         string            `json:"kind"`
	Phase        string            `json:"phase,omitempty"`
	NodeName     string            `json:"nodeName,omitempty"`
	Labels       map[string]string `json:"labels,omitempty"`
	Conditions   []string          `json:"conditions,omitempty"`
	Replicas     *ReplicaStatus    `json:"replicas,omitempty"`
	IsReady      bool              `json:"isReady"`
	IsRestarting bool              `json:"isRestarting"`
}

type ReplicaStatus struct {
	Desired   int32 `json:"desired"`
	Ready     int32 `json:"ready"`
	Available int32 `json:"available"`
}

// ImageSummary describes a container image in the workload.
type ImageSummary struct {
	Container string `json:"container"`
	Image     string `json:"image"`
	IsLatest  bool   `json:"isLatest"`
	IsInit    bool   `json:"isInit"`
}

// SecuritySummary captures security-relevant fields.
type SecuritySummary struct {
	RunAsNonRoot      *bool          `json:"runAsNonRoot,omitempty"`
	RunAsUser         *int64         `json:"runAsUser,omitempty"`
	ReadOnlyRootFS    *bool          `json:"readOnlyRootFS,omitempty"`
	AllowPrivilegeEsc *bool          `json:"allowPrivilegeEscalation,omitempty"`
	Privileged        *bool          `json:"privileged,omitempty"`
	Capabilities      []string       `json:"capabilities,omitempty"`
	SeccompProfile    string         `json:"seccompProfile,omitempty"`
	Containers        []ContainerSec `json:"containers,omitempty"`
}

// ContainerSec holds per-container security context details.
type ContainerSec struct {
	Name              string   `json:"name"`
	Privileged        bool     `json:"privileged"`
	RunAsNonRoot      *bool    `json:"runAsNonRoot,omitempty"`
	ReadOnlyRootFS    *bool    `json:"readOnlyRootFS,omitempty"`
	AllowPrivilegeEsc *bool    `json:"allowPrivilegeEscalation,omitempty"`
	Capabilities      []string `json:"capabilities,omitempty"`
}

// ServiceAccountSummary captures service account configuration.
type ServiceAccountSummary struct {
	Name                         string `json:"name"`
	AutomountServiceAccountToken *bool  `json:"automountServiceAccountToken,omitempty"`
	Exists                       bool   `json:"exists"`
	IsDefault                    bool   `json:"isDefault"`
}

// OwnerChain describes the ownership lineage (e.g. Pod → ReplicaSet → Deployment).
type OwnerChain struct {
	Entries []OwnerEntry `json:"entries"`
}

type OwnerEntry struct {
	Kind string `json:"kind"`
	Name string `json:"name"`
	UID  string `json:"uid"`
}

// EventSummary holds a summarised Kubernetes event.
type EventSummary struct {
	Type    string `json:"type"`
	Reason  string `json:"reason"`
	Message string `json:"message"`
	Count   int32  `json:"count"`
	Age     string `json:"age"`
}

// LogSnippet holds the tail of the most relevant container's logs.
type LogSnippet struct {
	Container string   `json:"container"`
	Lines     []string `json:"lines"`
	Truncated bool     `json:"truncated"`
	Error     string   `json:"error,omitempty"`
}

// NetworkSummary captures network policy and service binding context.
type NetworkSummary struct {
	HasNetworkPolicy bool             `json:"hasNetworkPolicy"`
	Policies         []string         `json:"policies,omitempty"`
	Services         []ServiceBinding `json:"services,omitempty"`
}

type ServiceBinding struct {
	Name  string   `json:"name"`
	Ports []string `json:"ports,omitempty"`
}

// RBACSummary holds a quick RBAC inspection result.
type RBACSummary struct {
	Bindings      []RoleBindingEntry `json:"bindings,omitempty"`
	CanExec       bool               `json:"canExec"`
	CanGetSecrets bool               `json:"canGetSecrets"`
	IsOverbroad   bool               `json:"isOverbroad"`
	Warnings      []string           `json:"warnings,omitempty"`
}

type RoleBindingEntry struct {
	BindingName string `json:"bindingName"`
	RoleName    string `json:"roleName"`
	RoleKind    string `json:"roleKind"`
	IsCluster   bool   `json:"isCluster"`
}
