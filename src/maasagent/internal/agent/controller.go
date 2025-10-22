// Copyright (c) 2023-2024 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package agent

import (
	"encoding/json"
	"fmt"
	"net/url"

	"gopkg.in/yaml.v3"
)

// Controller represents a MAAS controller that the agent communicates with.
//
// It includes the API endpoint URL and the fingerprint used to validate
// the controller's TLS certificate.
type Controller struct {
	URL         *url.URL `json:"-" yaml:"-"`
	Fingerprint string   `json:"fingerprint"`
}

// MarshalJSON implements the json.Marshaler interface for Controller.
// It converts the Controller to JSON format, including the URL as a string.
func (c *Controller) MarshalJSON() ([]byte, error) {
	var url string

	if c.URL != nil {
		url = c.URL.String()
	}

	return json.Marshal(
		struct {
			Fingerprint string `json:"fingerprint"`
			URL         string `json:"url"`
		}{
			Fingerprint: c.Fingerprint,
			URL:         url,
		},
	)
}

// UnmarshalJSON implements the json.Unmarshaler interface for Controller.
// It parses JSON data into a Controller, converting the URL string to a url.URL.
func (c *Controller) UnmarshalJSON(data []byte) error {
	var t struct {
		Fingerprint string `json:"fingerprint"`
		URL         string `json:"url"`
	}

	if err := json.Unmarshal(data, &t); err != nil {
		return err
	}

	url, err := url.Parse(t.URL)
	if err != nil {
		return fmt.Errorf("invalid URL: %w", err)
	}

	c.Fingerprint = t.Fingerprint
	c.URL = url

	return nil
}

// MarshalYAML implements the yaml.Marshaler interface for Controller.
// It converts the Controller to YAML format, including the URL as a string.
func (c *Controller) MarshalYAML() (any, error) {
	var url string

	if c.URL != nil {
		url = c.URL.String()
	}

	return struct {
		Fingerprint string `yaml:"fingerprint"`
		URL         string `yaml:"url"`
	}{
		Fingerprint: c.Fingerprint,
		URL:         url,
	}, nil
}

// UnmarshalYAML implements the yaml.Unmarshaler interface for Controller.
// It parses YAML data into a Controller, converting the URL string to a url.URL.
func (c *Controller) UnmarshalYAML(value *yaml.Node) error {
	var t struct {
		Fingerprint string `yaml:"fingerprint"`
		URL         string `yaml:"url"`
	}

	if err := value.Decode(&t); err != nil {
		return err
	}

	url, err := url.Parse(t.URL)
	if err != nil {
		return err
	}

	c.Fingerprint = t.Fingerprint
	c.URL = url

	return nil
}
