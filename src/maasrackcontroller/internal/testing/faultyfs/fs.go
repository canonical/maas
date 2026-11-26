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

package faultyfs

import (
	"fmt"

	"github.com/spf13/afero"
)

type Fs struct {
	afero.Fs
	failPath string
}

func NewFs(fs afero.Fs) *Fs {
	return &Fs{
		Fs: fs,
	}
}

func (f *Fs) SetFailPath(path string) {
	f.failPath = path
}

func (f *Fs) Rename(oldname, newname string) error {
	if newname == f.failPath {
		return fmt.Errorf("injected fault for %s", newname)
	}

	return f.Fs.Rename(oldname, newname)
}
