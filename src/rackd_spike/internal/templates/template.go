package templates

import (
	"embed"
	"io"
	"strings"
	"text/template"
)

//go:embed dhcpd6.conf.template
//go:embed dhcpd.conf.template
var tmpls embed.FS

type TemplateData struct{}

func (t TemplateData) SplitLines(s string) []string {
	return strings.Split(s, "\n")
}

func (t TemplateData) Replace(s, orig, sub string) string {
	return strings.ReplaceAll(s, orig, sub)
}

func (t TemplateData) CommaList(l []string) string {
	return strings.Join(l, ", ")
}

func (t TemplateData) QuotedCommaList(l []string) string {
	for i, word := range l {
		if word[0] != '"' {
			word = string(append([]byte{'"'}, word...))
		}
		if word[len(word)-1] != '"' {
			word = string(append([]byte(word), '"'))
		}
		l[i] = word
	}
	return t.CommaList(l)
}

func (t TemplateData) OneLine(s string) string {
	return strings.ReplaceAll(s, "\n", " ")
}

func Render(dest io.Writer, data interface{}, fileName string) (err error) {
	tmpl, err := template.ParseFS(tmpls, fileName)
	if err != nil {
		return err
	}
	return tmpl.Execute(dest, data)
}
