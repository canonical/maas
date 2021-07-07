package machinehelpers

import (
	"errors"
	"io"
	"testing"
)

type mockLeaseFile struct {
	Data []byte
}

func (m mockLeaseFile) Read(b []byte) (n int, err error) {
	n = copy(b, m.Data)
	if n > 0 {
		m.Data = m.Data[n:]
	}
	if len(m.Data) == 0 {
		return n, io.EOF
	}
	return n, nil
}

func TestGetLatestFixedAddress(t *testing.T) {
	table := []struct {
		Name string
		In   mockLeaseFile
		Out  string
		Err  error
	}{
		{
			Name: "basic-v4-lease-file",
			In: mockLeaseFile{
				Data: []byte(`
	lease {
		fixed-address 10.0.0.2;
	}
				`),
			},
			Out: "10.0.0.2",
		}, {
			Name: "basic-v6-lease-file",
			In: mockLeaseFile{
				Data: []byte(`
	lease {
		fixed-address6 fe80::ca56:eed8:1344:1aa2;
	}
				`),
			},
			Out: "fe80::ca56:eed8:1344:1aa2",
		}, {
			Name: "no-data-lease-file",
			In:   mockLeaseFile{},
		}, {
			Name: "multi-lease-lease-file",
			In: mockLeaseFile{
				Data: []byte(`
	lease {
		fixed-address 10.0.0.9;
	}

	lease {
		fixed-address 10.0.0.2;
	}
				`),
			},
			Out: "10.0.0.2",
		},
	}
	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			out, err := getLatestFixedAddress(tcase.In)
			if !errors.Is(err, tcase.Err) {
				tt.Fatalf("expected %v to equal %v", err, tcase.Err)
			}
			if out != tcase.Out {
				tt.Fatalf("expected '%s' to equal '%s'", out, tcase.Out)
			}
		})
	}
}
