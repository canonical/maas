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

package httpproxy

import (
	"net/url"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestURLTracker(t *testing.T) {
	type in struct {
		targets []*url.URL
	}

	type out struct {
		errorExpected   bool
		reliableCount   int
		unreliableCount int
	}

	testcases := map[string]struct {
		in  in
		out out
	}{
		"New tracker starts with all reliable": {
			in: in{
				targets: []*url.URL{
					{Host: "example1.com"},
					{Host: "example2.com"},
				},
			},
			out: out{reliableCount: 2, unreliableCount: 0},
		},
		"New tracker with no trackers returns error": {
			in: in{
				targets: []*url.URL{},
			},
			out: out{errorExpected: true},
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			tracker, err := NewURLTracker(tc.in.targets)
			if tc.out.errorExpected {
				assert.NotNil(t, err)
				return
			}

			assert.Nil(t, err)
			assert.Equal(t, tc.out.reliableCount, len(tracker.reliable))
			assert.Equal(t, tc.out.unreliableCount, len(tracker.unreliable))
		})
	}
}

func TestURLTracker_RecordFailure_MovesToUnreliable(t *testing.T) {
	url1, _ := url.Parse("http://example1.com")
	targets := []*url.URL{url1}

	tracker, _ := NewURLTracker(targets)

	// Record 5 consecutive failures
	for i := 0; i < maxConsecutiveFailures; i++ {
		tracker.RecordFailure(url1)
	}

	// Should be moved to unreliable
	assert.Len(t, tracker.reliable, 0)
	assert.Len(t, tracker.unreliable, 1)
}

func TestURLTracker_RecordSuccess_MovesToReliable(t *testing.T) {
	url1, _ := url.Parse("http://example1.com")
	targets := []*url.URL{url1}

	tracker, _ := NewURLTracker(targets)

	// Move to unreliable first
	for i := 0; i < maxConsecutiveFailures; i++ {
		tracker.RecordFailure(url1)
	}

	assert.Len(t, tracker.unreliable, 1)

	// Record success should move back to reliable
	tracker.RecordSuccess(url1)

	assert.Len(t, tracker.reliable, 1)
	assert.Len(t, tracker.unreliable, 0)
}

func TestURLTracker_RecordSuccess_ResetsFailureCount(t *testing.T) {
	url1, _ := url.Parse("http://example1.com")
	targets := []*url.URL{url1}

	tracker, _ := NewURLTracker(targets)

	// Record some failures
	tracker.RecordFailure(url1)
	tracker.RecordFailure(url1)
	assert.Equal(t, 2, tracker.reliable[url1.String()].consecutiveFailures)

	// Record success should reset count
	tracker.RecordSuccess(url1)
	assert.Equal(t, 0, tracker.reliable[url1.String()].consecutiveFailures)
}

func TestURLTracker_SelectURL_OnlyUnreliable(t *testing.T) {
	url1, _ := url.Parse("http://example1.com")
	targets := []*url.URL{url1}

	tracker, _ := NewURLTracker(targets)

	// Move to unreliable
	for i := 0; i < maxConsecutiveFailures; i++ {
		tracker.RecordFailure(url1)
	}

	// Should still be able to select from unreliable
	selected := tracker.SelectURL(nil)

	assert.NotNil(t, selected)
	assert.Equal(t, url1.String(), selected.String())
}

func TestURLTracker_SelectURL_Distribution(t *testing.T) {
	url1, _ := url.Parse("http://reliable.com")
	url2, _ := url.Parse("http://unreliable.com")
	targets := []*url.URL{url1, url2}

	tracker, _ := NewURLTracker(targets)

	// Move url2 to unreliable
	for i := 0; i < maxConsecutiveFailures; i++ {
		tracker.RecordFailure(url2)
	}

	// Run many selections and verify we mostly get reliable
	reliableCount := 0
	unreliableCount := 0
	iterations := 1000

	for i := 0; i < iterations; i++ {
		selected := tracker.SelectURL(nil)
		if selected.String() == url1.String() {
			reliableCount++
		} else {
			unreliableCount++
		}
	}

	// Should be roughly 95% reliable, 5% unreliable
	// Allow some variance due to randomness: check reliable is between 90% and 99% - this test may occasionally fail due to
	// randomness but the event is statistically extremely rare (around 1 fail every trillion executions).
	reliableRatio := float64(reliableCount) / float64(iterations)
	assert.Greater(t, reliableRatio, 0.90)
	assert.Less(t, reliableRatio, 1.0)
}

func TestURLTracker_RecordFailure_UntrackedURL(t *testing.T) {
	u, _ := url.Parse("http://foo.com")
	tracker, _ := NewURLTracker([]*url.URL{u})

	uknwown, _ := url.Parse("http://example.com")

	assert.NotPanics(t, func() {
		tracker.RecordFailure(uknwown)
	})
}

func TestURLTracker_RecordSuccess_UntrackedURL(t *testing.T) {
	u, _ := url.Parse("http://foo.com")
	tracker, _ := NewURLTracker([]*url.URL{u})

	uknwown, _ := url.Parse("http://example.com")

	assert.NotPanics(t, func() {
		tracker.RecordSuccess(uknwown)
	})
}

func TestURLTrackerSelectURL(t *testing.T) {
	type in struct {
		targets []*url.URL
		exclude []string
	}

	type out struct {
		acceptableUrls []string
	}

	testcases := map[string]struct {
		in  in
		out out
	}{
		"Exclude one of two reliable URLs": {
			in: in{
				targets: []*url.URL{
					{Host: "example1.com"},
					{Host: "example2.com"},
				},
				exclude: []string{"//example1.com"},
			},
			out: out{
				acceptableUrls: []string{"//example2.com"}},
		},
		"Exclude all reliable URLs": {
			in: in{
				targets: []*url.URL{
					{Host: "example1.com"},
					{Host: "example2.com"},
				},
				exclude: []string{"//example1.com", "//example2.com"},
			},
			out: out{
				acceptableUrls: nil,
			},
		},
		"Exclude unknown URL does not crash": {
			in: in{
				targets: []*url.URL{
					{Host: "example1.com"},
					{Host: "example2.com"},
				},
				exclude: []string{"//example3.com"},
			},
			out: out{
				acceptableUrls: []string{"//example1.com", "//example2.com"},
			},
		},
		"Exclude none": {
			in: in{
				targets: []*url.URL{
					{Host: "example1.com"},
					{Host: "example2.com"},
				},
				exclude: []string{},
			},
			out: out{
				acceptableUrls: []string{"//example1.com", "//example2.com"},
			},
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			tracker, _ := NewURLTracker(tc.in.targets)

			selected := tracker.SelectURL(tc.in.exclude)
			if tc.out.acceptableUrls == nil {
				assert.Nil(t, selected)
			} else {
				assert.NotNil(t, selected)
				assert.Contains(t, tc.out.acceptableUrls, selected.String())
			}
		})
	}
}
