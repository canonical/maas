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
	"encoding/base64"
	"encoding/json"
	"fmt"
)

// BootstrapToken is used to authenticate MAAS Agent during enrollment.
type BootstrapToken struct {
	Secret      string       `json:"secret"`
	Controllers []Controller `json:"controllers"`
}

// MarshalText encodes BootstrapToken into Base64 encoded JSON
func (t BootstrapToken) MarshalText() (string, error) {
	jsonBytes, err := json.Marshal(t)
	if err != nil {
		return "", fmt.Errorf("failed to marshal JSON: %w", err)
	}

	return base64.StdEncoding.EncodeToString(jsonBytes), nil
}

// UnmarshalText decodes base64 encoded JSON into the BootstrapToken
func (t *BootstrapToken) UnmarshalText(data string) error {
	decoded, err := base64.StdEncoding.DecodeString(data)
	if err != nil {
		return fmt.Errorf("failed to decode base64: %w", err)
	}

	if err := json.Unmarshal(decoded, t); err != nil {
		return fmt.Errorf("failed to unmarshal JSON: %w", err)
	}

	return nil
}
