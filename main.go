package main

import (
    "fmt"
    "html/template"
    "log"
    "net/http"
    "os"
    "strings"
    "path/filepath"
    "strconv"
)

type MembersData struct {
    AddressLine1 string
    Members []string
}

type MemberData struct {
    FirstName string
    MiddleNames string
    LastName string
}

type VisitorData struct {
    VisitorNumber int
}

var pages = ParseTemplates()

var MEMBERS_PAGES = []string{
    "introduction",
    "permanent-or-family-home",
    "household-composition",
    "everyone-at-address-confirmation",
    "overnight-visitors",
    "household-relationships",
    "completed",
}

var HOUSEHOLD_PAGES = []string{
    "introduction",
    "type-of-accommodation",
    "type-of-house",
    "self-contained-accommodation",
    "number-of-bedrooms",
    "central-heating",
    "own-or-rent",
    "number-of-vehicles",
    "completed",
}

var MEMBER_PAGES = []string{
    "introduction",
    "details-correct",
    "over-16",
    "private-response",
    "sex",
    "date-of-birth",
    "marital-status",
    "another-address",
    "other-address",
    "address-type",
    "in-education",
    "term-time-location",
    "country-of-birth",
    "carer",
    "national-identity",
    "ethnic-group",
    "other-ethnic-group",
    "language",
    "religion",
    "past-usual-address",
    "passports",
    "disability",
    "qualifications",
    "employment-type",
    "jobseeker",
    "job-availability",
    "job-pending",
    "occupation",
    "ever-worked",
    "main-job",
    "hours-worked",
    "work-travel",
    "job-title",
    "job-description",
    "main-job-type",
    "business-name",
    "employers-business",
    "completed",
}

var VISITOR_PAGES = []string{
    "name",
    "sex",
    "date-of-birth",
    "uk-resident",
    "address",
    "completed",
}

func handle_session(w http.ResponseWriter, r *http.Request) {
    // TODO decode JTI, create cookie session

    redirect(w, r, "/introduction")
}

func handle_introduction(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        // TODO save answers
        redirect(w, r, "/address")
        return
    }

    pages.ExecuteTemplate(w, "introduction", "")
}

func handle_address(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        // TODO save answers
        redirect(w, r, "/members/introduction")
        return
    }

    pages.ExecuteTemplate(w, "address", "")
}

func handle_members(w http.ResponseWriter, r *http.Request) {
    page := r.URL.Path[len("/members/"):]

    if r.Method == http.MethodPost {
        // TODO save answers

        i := index(MEMBERS_PAGES, page) + 1

        next := "/household/introduction"
        if i < len(MEMBERS_PAGES) {
            next = "/members/" + MEMBERS_PAGES[i]
        }

        redirect(w, r, next)
        return
    }

    data := MembersData{ // TODO
        AddressLine1: "44 hill side",
        Members: []string{
            "Danny K Boje",
            "Anjali M Yo",
        },
    }
    pages.ExecuteTemplate(w, "members/" + page, data)
}

func handle_household(w http.ResponseWriter, r *http.Request) {
    page := r.URL.Path[len("/household/"):]

    if r.Method == http.MethodPost {
        // TODO save answers

        i := index(HOUSEHOLD_PAGES, page) + 1

        next := "/member/0/introduction"
        if i < len(HOUSEHOLD_PAGES) {
            next = "/household/" + HOUSEHOLD_PAGES[i]
        }

        redirect(w, r, next)
        return
    }

    pages.ExecuteTemplate(w, "household/" + page, "")
}

func handle_member(w http.ResponseWriter, r *http.Request) {
    parts := strings.Split(r.URL.Path, "/")
    group_instance, _ := strconv.Atoi(parts[2])
    page := parts[3]

    if r.Method == http.MethodPost {
        // TODO save answers

        if page == "private-response" {
            if r.FormValue("private-response-answer")[:3] == "Yes" {
                redirect(w, r, fmt.Sprintf("/member/%v/request-private-response", group_instance))
                return
            }
        }

        if page == "request-private-response" {
            redirect(w, r, fmt.Sprintf("/member/%v/completed", group_instance))
            return
        }

        num_members := 2 // TODO

        i := index(MEMBER_PAGES, page) + 1

        next := "/visitors_introduction"
        if i < len(MEMBER_PAGES) {
            next = fmt.Sprintf("/member/%v/%v", group_instance, MEMBER_PAGES[i])
        } else if group_instance + 1 < num_members {
            next = fmt.Sprintf("/member/%v/introduction", (group_instance + 1))
        }

        redirect(w, r, next)
        return
    }

    data := MemberData{ // TODO
        FirstName: "Danny",
        MiddleNames: "K",
        LastName: "Boje",
    }
    if group_instance == 1 {
        data = MemberData{
            FirstName: "Anjali",
            MiddleNames: "M",
            LastName: "Yo",
        }
    }
    pages.ExecuteTemplate(w, "member/" + page, data)
}

func handle_visitors_introduction(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        // TODO save answers
        redirect(w, r, "/visitor/0/name")
        return
    }

    pages.ExecuteTemplate(w, "visitors_introduction", "")
}

func handle_visitor(w http.ResponseWriter, r *http.Request) {
    parts := strings.Split(r.URL.Path, "/")
    group_instance, _ := strconv.Atoi(parts[2])
    page := parts[3]

    if r.Method == http.MethodPost {
        // TODO save answers

        num_visitors := 2 // TODO

        i := index(VISITOR_PAGES, page) + 1

        next := "/visitors_completed"
        if i < len(VISITOR_PAGES) {
            next = fmt.Sprintf("/visitor/%v/%v", group_instance, VISITOR_PAGES[i])
        } else if group_instance + 1 < num_visitors {
            next = fmt.Sprintf("/visitor/%v/name", (group_instance + 1))
        }

        redirect(w, r, next)
        return
    }

    data := VisitorData{
        VisitorNumber: group_instance + 1,
    }
    pages.ExecuteTemplate(w, "visitor/" + page, data)
}

func handle_visitors_completed(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        // TODO save answers
        redirect(w, r, "/completed")
        return
    }

    pages.ExecuteTemplate(w, "visitors_completed", "")
}

func handle_completed(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        // TODO validate and submit answers
        log.Print("Submitting answers")
        redirect(w, r, "/thank-you")
        return
    }

    pages.ExecuteTemplate(w, "completed", "")
}

func handle_thank_you(w http.ResponseWriter, r *http.Request) {
    pages.ExecuteTemplate(w, "thank-you", "")
}

func handle_submission(w http.ResponseWriter, r *http.Request) {
    fmt.Fprintf(w, "{}")
}

func index(slice []string, item string) int {
    for i, _ := range slice {
        if slice[i] == item {
            return i
        }
    }
    return -1
}

func redirect(w http.ResponseWriter, r *http.Request, path string) {
    http.Redirect(w, r, "http://" + r.Host + path, http.StatusFound)
}

func ParseTemplates() *template.Template {
    templ := template.New("")
    err := filepath.Walk("./flat_templates", func(path string, info os.FileInfo, err error) error {
        if strings.Contains(path, ".html") {
            _, err = templ.ParseFiles(path)
            if err != nil {
                log.Println(err)
            }
        }

        return err
    })

    if err != nil {
        panic(err)
    }

    return templ
}

func main() {
    fs := http.FileServer(http.Dir("static"))
    http.Handle("/static/", http.StripPrefix("/static/", fs))
    http.HandleFunc("/session", handle_session)
    http.HandleFunc("/introduction", handle_introduction)
    http.HandleFunc("/address", handle_address)
    http.HandleFunc("/members/", handle_members)
    http.HandleFunc("/household/", handle_household)
    http.HandleFunc("/member/", handle_member)
    http.HandleFunc("/visitors_introduction", handle_visitors_introduction)
    http.HandleFunc("/visitor/", handle_visitor)
    http.HandleFunc("/visitors_completed", handle_visitors_completed)
    http.HandleFunc("/completed", handle_completed)
    http.HandleFunc("/thank-you", handle_thank_you)
    http.HandleFunc("/dump/submission", handle_submission)
    log.Fatal(http.ListenAndServe(":8080", nil))
}
