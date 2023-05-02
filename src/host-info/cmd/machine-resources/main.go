// Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
// GNU Affero General Public License version 3 (see the file LICENSE).

package main

import (
	"encoding/json"
	"fmt"
	"os"

	"host-info/pkg/info"
)

func checkError(err error) {
	if err == nil {
		return
	}

	fmt.Fprintf(os.Stderr, "ERROR: %v\n", err)
	os.Exit(1)
}

func main() {
	data, err := info.GetInfo()
	checkError(err)

	encoder := json.NewEncoder(os.Stdout)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "    ")
	err = encoder.Encode(data)
	checkError(err)
}
