// Copyright (c) 2026 Canonical Ltd
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

package client

// EnrollRequest contains data that agent can/should present during enrollment.
type EnrollRequest struct {
	Secret string `json:"secret"`
	// Optional: Only for new identity
	CSR string `json:"csr,omitempty"`
	// Optional: For existing identity
	AgentUUID string `json:"agent_uuid,omitempty"`
}

// EnrollResponse contains the data returned after a successful enrollment.
type EnrollResponse struct {
	Certificate string `json:"certificate"`
	CA          string `json:"ca"`
}

// TemporalConfig holds Temporal-specific configuration.
type TemporalConfig struct {
	EncryptionKey string `json:"encryption_key"`
}

// ConfigResponse contains the configuration data returned by the controller.
type ConfigResponse struct {
	Temporal  TemporalConfig `json:"temporal"`
	SystemID  string         `json:"system_id"`
	RPCSecret string         `json:"rpc_secret"`
	MAASURL   string         `json:"maas_url"`
}
