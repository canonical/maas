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

package atomicfile

import (
	"os"
	"path/filepath"
)

// WriteFile writes data to a temporary filename.tmp, then replaces an existing
// file with the same name atomically.
// However on non-Unix platforms os.Rename is not an atomic operation, hence the
// whole WriteFile is not atomic.
//
//nolint:nonamedreturns // named return is needed for cleanup
func WriteFile(filename string, data []byte, perm os.FileMode) (err error) {
	tf, err := os.CreateTemp(filepath.Dir(filename), filepath.Base(filename)+".*.tmp")
	if err != nil {
		return err
	}

	tname := tf.Name()

	defer func() {
		if err != nil {
			//nolint:errcheck,gosec // we already return a more important error
			tf.Close()
			//nolint:errcheck,gosec // we already return a more important error
			os.Remove(tname)
		}
	}()

	if _, err := tf.Write(data); err != nil {
		return err
	}

	if err := tf.Chmod(perm); err != nil {
		return err
	}

	if err := tf.Sync(); err != nil {
		return err
	}

	if err := tf.Close(); err != nil {
		return err
	}

	return os.Rename(tname, filename)
}
