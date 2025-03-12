// Copyright (c) 2025 Canonical Ltd
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

package resolver

import (
	"strings"

	"github.com/miekg/dns"
)

const (
	// max fqdn length is 255, 127 is a rounded number of
	// possible labels of the smallest length that can fit
	// into that max fqdn length
	maxRecursionDepth = 127
)

type queryState struct {
	lastResponse    dns.RR
	mostSpecificNS  *dns.NS
	currentLabel    string
	labels          []string
	currentLabelIdx int
	recursionDepth  int
}

func newQueryState(fqdn string) *queryState {
	var labels []string

	if fqdn == "." {
		labels = []string{fqdn}
	} else {
		labels = strings.Split(dns.Fqdn(fqdn), ".")
	}

	return &queryState{
		labels: labels,
	}
}

func (q *queryState) NextLabel() (string, bool) {
	if len(q.labels) == q.currentLabelIdx || !q.CanContinue() {
		return q.currentLabel, false
	}

	subLabel := q.labels[len(q.labels)-(q.currentLabelIdx+1):]
	if len(subLabel) == 1 {
		q.currentLabel = subLabel[0]

		if q.currentLabel == "" {
			q.currentLabel = "."
		}

		q.currentLabelIdx++
		q.recursionDepth++

		return dns.Fqdn(q.currentLabel), len(subLabel) < len(q.labels)
	}

	q.currentLabel = dns.Fqdn(strings.Join(subLabel, "."))

	q.currentLabelIdx++
	q.recursionDepth++

	return q.currentLabel, len(subLabel) < len(q.labels)
}

func (q *queryState) SetLastResponse(rr dns.RR) {
	if ns, ok := rr.(*dns.NS); ok {
		if q.mostSpecificNS == nil || len(q.mostSpecificNS.Header().Name) < len(ns.Header().Name) {
			q.mostSpecificNS = ns
		}
	}

	q.lastResponse = rr
}

func (q *queryState) LastResponse() dns.RR {
	return q.lastResponse
}

func (q *queryState) Nameserver() *dns.NS {
	return q.mostSpecificNS
}

func (q *queryState) UseSearch() bool {
	return len(q.labels) == 2 // . and name
}

func (q *queryState) CanContinue() bool {
	return q.recursionDepth < maxRecursionDepth
}
