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

package agent_test

import (
	"net/url"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gopkg.in/yaml.v3"
	"maas.io/core/src/maasagent/internal/agent"
)

func TestController_MarshalUnmarshalJSON(t *testing.T) {
	u, err := url.Parse("https://maas.internal")
	require.NoError(t, err)

	expected := agent.Controller{
		URL:         u,
		Fingerprint: "maas",
	}

	jsonData, err := expected.MarshalJSON()
	require.NoError(t, err)

	var actual agent.Controller
	require.NoError(t, actual.UnmarshalJSON(jsonData))

	assert.Equal(t, expected.Fingerprint, actual.Fingerprint)
	assert.Equal(t, expected.URL.String(), actual.URL.String())
}

func TestController_MarshalUnmarshalYAML(t *testing.T) {
	u, err := url.Parse("https://maas.internal")
	require.NoError(t, err)

	expected := agent.Controller{
		URL:         u,
		Fingerprint: "maas",
	}

	yamlData, err := yaml.Marshal(&expected)
	require.NoError(t, err)

	var actual agent.Controller
	require.NoError(t, yaml.Unmarshal(yamlData, &actual))

	assert.Equal(t, expected.Fingerprint, actual.Fingerprint)
	assert.Equal(t, expected.URL.String(), actual.URL.String())
}
