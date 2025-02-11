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

package tag

type builder struct {
	KeyVals []any
}

func Builder() *builder {
	return &builder{}
}

// TargetSystemID provides KV with a tag for the given systemID
func (b *builder) TargetSystemID(systemID string) *builder {
	return b.KV("target_system_id", systemID)
}

// Error provides a KV with a tag for the given error
func (b *builder) Error(err error) *builder {
	return b.KV("error", err)
}

func (b *builder) KV(key, value any) *builder {
	b.KeyVals = append(b.KeyVals, key, value)
	return b
}
