package kubernetes

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
)

type PodImage struct {
	Namespace  string
	PodName    string
	Container  string
	Image      string
}

type Client struct {
	context string
}

func NewClient(context string) *Client {
	return &Client{context: context}
}

func (c *Client) GetPodImages(namespace string) ([]PodImage, error) {
	args := []string{"get", "pods", "-o", "json"}
	if namespace != "" {
		args = append(args, "-n", namespace)
	} else {
		args = append(args, "--all-namespaces")
	}

	cmd := exec.Command("kubectl", args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("kubectl failed: %s", stderr.String())
	}

	var result struct {
		Items []struct {
			Metadata struct {
				Name      string `json:"name"`
				Namespace string `json:"namespace"`
			} `json:"metadata"`
			Spec struct {
				Containers []struct {
					Name  string `json:"name"`
					Image string `json:"image"`
				} `json:"containers"`
			} `json:"spec"`
		} `json:"items"`
	}

	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		return nil, fmt.Errorf("failed to parse kubectl output: %w", err)
	}

	var images []PodImage
	seen := make(map[string]bool)

	for _, pod := range result.Items {
		for _, container := range pod.Spec.Containers {
			key := fmt.Sprintf("%s/%s", pod.Metadata.Namespace, container.Image)
			if !seen[key] {
				seen[key] = true
				images = append(images, PodImage{
					Namespace: pod.Metadata.Namespace,
					PodName:   pod.Metadata.Name,
					Container: container.Name,
					Image:     container.Image,
				})
			}
		}
	}

	return images, nil
}

func (c *Client) IsClusterAccessible() bool {
	cmd := exec.Command("kubectl", "cluster-info")
	return cmd.Run() == nil
}

func (c *Client) GetCurrentContext() (string, error) {
	cmd := exec.Command("kubectl", "config", "current-context")
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(output)), nil
}
