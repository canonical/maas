package drivers

import "regexp"

var (
	IPExtractorIdentity = regexp.MustCompile("^(?P<address>.+?)$")
	IPExtractorURL      = regexp.MustCompile(`(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}`)
)

type IPExtractor struct {
	Field   string
	Pattern *regexp.Regexp
}

func NewIPExtractor(fieldName string, pattern *regexp.Regexp) IPExtractor {
	return IPExtractor{
		Field:   fieldName,
		Pattern: pattern,
	}
}
