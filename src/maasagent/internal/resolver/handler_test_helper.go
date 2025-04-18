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
	"bufio"
	"bytes"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
	"testing"

	"github.com/miekg/dns"
)

// ParseDigOutputBlock parses a testdata file and extracts the content
// of a specific block. Anything starting with "#" is considered to be a block.
//
// Example:
// # Request
// ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1
// ;; flags: rd; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0
//
// ;; QUESTION SECTION:
// ;example.com.	IN	 A
//
// # DNS Resolution
// ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1
// ;; flags: rd; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0
//
// ;; QUESTION SECTION:
// ;example.com.	IN	 A
//
// ;; ANSWER SECTION:
// example.com.	30	IN	A	10.0.0.1
//
// # Response
// ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1
// ;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0
//
// ;; QUESTION SECTION:
// ;example.com.	IN	 A
//
// ;; ANSWER SECTION:
// example.com.	30	IN	A	10.0.0.1
func ParseDigOutputBlock(tb testing.TB, file string, block string) []*dns.Msg {
	tb.Helper()

	data, err := os.ReadFile(file) //nolint: gosec // G304. Thats a fixture!
	if err != nil {
		tb.Errorf("failed to read test file %q: %v", file, err)
	}

	var lines []string

	inSection := false

	scanner := bufio.NewScanner(bytes.NewReader(data))

	for scanner.Scan() {
		line := scanner.Text()

		if strings.HasPrefix(line, "#") {
			if strings.TrimSpace(strings.TrimPrefix(line, "#")) == block {
				inSection = true
				lines = []string{}

				continue
			}

			if inSection {
				break
			}
		}

		if inSection {
			lines = append(lines, line)
		}
	}

	if err = scanner.Err(); err != nil {
		tb.Fatalf("error reading file: %v", err)
	}

	messages, err := ParseDigOutput(strings.Join(lines, "\n"))
	if err != nil {
		tb.Fatal(err)
	}

	return messages
}

type ParserFunc func(data string, msg *dns.Msg) error

var sectionParsers = map[string]ParserFunc{
	"HEADER":     parseDigHeader,
	"FLAGS":      parseDigFlags,
	"QUESTION":   parseDigQuestion,
	"ANSWER":     parseDigAnswer,
	"ADDITIONAL": parseDigAdditional,
	"AUTHORITY":  parseDigAuthority,
}

func ParseDigOutput(data string) ([]*dns.Msg, error) {
	const (
		headerSection     = ";; ->>HEADER<<- "
		flagsSection      = ";; flags: "
		questionSection   = ";; QUESTION SECTION:"
		answerSection     = ";; ANSWER SECTION:"
		additionalSection = ";; ADDITIONAL SECTION:"
		authoritySection  = ";; AUTHORITY SECTION:"
	)

	var messages []*dns.Msg

	m := &dns.Msg{
		Question: []dns.Question{},
		Answer:   []dns.RR{},
		Extra:    []dns.RR{},
	}
	s := bufio.NewScanner(strings.NewReader(data))

	currentParser := (ParserFunc)(nil)

	for s.Scan() {
		line := s.Text()

		switch {
		case strings.HasPrefix(line, headerSection):
			currentParser = sectionParsers["HEADER"]

			if m.Id > 0 {
				messages = append(messages, m)
				m = &dns.Msg{}
			}
		case strings.HasPrefix(line, flagsSection):
			currentParser = sectionParsers["FLAGS"]
		case strings.HasPrefix(line, questionSection):
			currentParser = sectionParsers["QUESTION"]
			continue
		case strings.HasPrefix(line, answerSection):
			currentParser = sectionParsers["ANSWER"]
			continue
		case strings.HasPrefix(line, additionalSection):
			currentParser = sectionParsers["ADDITIONAL"]
			continue
		case strings.HasPrefix(line, authoritySection):
			currentParser = sectionParsers["AUTHORITY"]
			continue
		}

		if currentParser != nil {
			if err := currentParser(line, m); err != nil {
				return nil, fmt.Errorf("failed to parse section: %v", err)
			}
		}
	}

	if m.Id > 0 {
		messages = append(messages, m)
	}

	if err := s.Err(); err != nil {
		return nil, fmt.Errorf("error reading input: %v", err)
	}

	// XXX: not ideal, but this is the easiest way to ensure we didn't miss anything.
	// Otherwise parser would require proper set of unit tests to cover every
	// possible scenario.
	if err := verify(data, messages); err != nil {
		return nil, err
	}

	return messages, nil
}

// This is a poor-man validation that parser works correctly. Messages are
// converted back to a dig-like format and compared with the input data.
func verify(data string, messages []*dns.Msg) error {
	expected := whitespaceNormalizer(data)

	// Package miekg/dns produces dig output without a ->>HEADER<<- section,
	// hence we need to remove it from the original dig input before we compare.
	expected = strings.Trim(strings.ReplaceAll(expected, "->>HEADER<<- ", ""), "\n")

	var sb strings.Builder
	for _, m := range messages {
		sb.WriteString(whitespaceNormalizer(m.String()) + "\n")
	}

	actual := strings.Trim(sb.String(), "\n")

	if expected != actual {
		return fmt.Errorf("data mismatch\nexpected:\n%v\n\nactual:\n%v", expected, actual)
	}

	return nil
}

func whitespaceNormalizer(data string) string {
	re := regexp.MustCompile(`\s+`)

	scanner := bufio.NewScanner(strings.NewReader(data))

	var result strings.Builder

	for scanner.Scan() {
		line := scanner.Text()

		if line != "" {
			result.WriteString(strings.TrimSpace(re.ReplaceAllString(line, " ")) + "\n")
		} else {
			result.WriteString("\n")
		}
	}

	return result.String()
}

// parseDigHeader sets header values on the provided *dns.Msg by parsing data:
// ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 1
func parseDigHeader(data string, m *dns.Msg) error {
	if strings.TrimSpace(data) == "" {
		return nil
	}

	headers := strings.Split(data[16:], ", ")
	for _, field := range headers {
		keyValue := strings.SplitN(field, ": ", 2)
		if len(keyValue) != 2 {
			continue // skip malformed entries
		}

		key, value := strings.TrimSpace(keyValue[0]), strings.TrimSpace(keyValue[1])

		switch key {
		case "opcode":
			m.Opcode = dns.StringToOpcode[value]
		case "status":
			m.Rcode = dns.StringToRcode[value]
		case "id":
			id, err := strconv.ParseUint(value, 10, 16)
			if err != nil {
				return fmt.Errorf("invalid ID value '%s': %w", value, err)
			}

			m.Id = uint16(id)
		}
	}

	return nil
}

// parseDigFlags set flags on the provided *dns.Msg by parsing data:
// ;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0
func parseDigFlags(data string, m *dns.Msg) error {
	if strings.TrimSpace(data) == "" {
		return nil
	}

	data, _, _ = strings.Cut(data[10:], ";")
	data = strings.TrimSpace(data)

	for _, flag := range strings.Fields(data) {
		switch flag {
		case "qr":
			m.Response = true
		case "rd":
			m.RecursionDesired = true
		case "ra":
			m.RecursionAvailable = true
		}
	}

	return nil
}

// parseDigQuestion sets values on the provided *dns.Msg by parsing data:
// ;; QUESTION SECTION:
// ;example.com.	IN	 A
func parseDigQuestion(data string, m *dns.Msg) error {
	if strings.TrimSpace(data) == "" {
		return nil
	}

	data = strings.TrimLeft(data, ";")

	rr, err := dns.NewRR(data)
	if err != nil {
		return err
	}

	m.Question = append(m.Question, dns.Question{
		Name:   strings.Fields(data)[0],
		Qtype:  rr.Header().Rrtype,
		Qclass: rr.Header().Class,
	})

	return nil
}

// parseDigAnswer sets values on the provided *dns.Msg by parsing data:
// ;; ANSWER SECTION:
// example.com.	30	IN	A	10.0.0.1
func parseDigAnswer(data string, m *dns.Msg) error {
	if strings.TrimSpace(data) == "" {
		return nil
	}

	rr, err := dns.NewRR(data)
	if err != nil {
		return err
	}

	m.Answer = append(m.Answer, rr)

	return nil
}

// parseDigAuthority sets values on the provided *dns.Msg by parsing data:
// ;; AUTHORITY SECTION:
// example.com. 3600 IN NS ns.example.com.
func parseDigAuthority(data string, m *dns.Msg) error {
	if strings.TrimSpace(data) == "" {
		return nil
	}

	rr, err := dns.NewRR(data)
	if err != nil {
		return err
	}

	m.Ns = append(m.Ns, rr)

	return nil
}

// parseDigAdditional sets values on the provided *dns.Msg by parsing data:
// ;; ADDITIONAL SECTION:
// maas.  30  IN  A  127.0.0.1
func parseDigAdditional(data string, m *dns.Msg) error {
	if strings.TrimSpace(data) == "" {
		return nil
	}

	rr, err := dns.NewRR(data)
	if err != nil {
		return err
	}

	m.Extra = append(m.Extra, rr)

	return nil
}

// extractQuestion creates a new Question message without including anything
// that belong to the answer.
func extractQuestion(message *dns.Msg) *dns.Msg {
	return &dns.Msg{
		MsgHdr: dns.MsgHdr{
			Id:                message.Id,
			Opcode:            message.Opcode,
			RecursionDesired:  message.RecursionDesired,
			AuthenticatedData: message.AuthenticatedData,
			CheckingDisabled:  message.CheckingDisabled,
		},
		Question: message.Question,
		Answer:   []dns.RR{},
		Ns:       []dns.RR{},
		Extra:    []dns.RR{},
	}
}

func extractQuestions(messages []*dns.Msg) []*dns.Msg {
	questions := make([]*dns.Msg, len(messages))

	for i, m := range messages {
		questions[i] = extractQuestion(m)
	}

	return questions
}
