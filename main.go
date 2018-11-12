package main

import (
    "fmt"
    "time"
    "html/template"
    "log"
    "net/http"
    "os"
    "strings"
    "path/filepath"
    "strconv"
    "encoding/json"
    "github.com/satori/go.uuid"
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

type AnswerData struct {
    AnswerId string
    AnswerInstance int
    GroupInstance int
    Value string
}

var pages = ParseTemplates()

var storage = map[string]map[string]string{}

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

    user_id := uuid.Must(uuid.NewV4())
    user_ik := uuid.Must(uuid.NewV4())

    expiration := time.Now().Add(time.Hour)
    http.SetCookie(w, &http.Cookie{Name: "user_id", Value: user_id.String(), Expires: expiration})
    http.SetCookie(w, &http.Cookie{Name: "user_ik", Value: user_ik.String(), Expires: expiration})

    redirect(w, r, "/introduction")
}

func handle_introduction(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        answers := parse_answers(r, 0)
        update_answers(r, answers)
        redirect(w, r, "/address")
        return
    }

    pages.ExecuteTemplate(w, "introduction", "")
}

func handle_address(w http.ResponseWriter, r *http.Request) {
    if r.Method == http.MethodPost {
        answers := parse_answers(r, 0)
        update_answers(r, answers)
        redirect(w, r, "/members/introduction")
        return
    }

    pages.ExecuteTemplate(w, "address", "")
}

func handle_members(w http.ResponseWriter, r *http.Request) {
    page := r.URL.Path[len("/members/"):]

    if r.Method == http.MethodPost {
        var answers map[string]string
        if page == "household-composition" {
            answers = map[string]string{}
            r.ParseForm()
            for k, v := range r.Form {
                if k[:10] == "household-" {
                    parts := strings.SplitN(k, "-", 3)
                    answer_instance, _ := strconv.Atoi(parts[1])
                    answers[ak(parts[2], answer_instance, 0)] = v[0]
                }
            }
        } else if page == "household-relationships" {
            answers = map[string]string{}
            r.ParseForm()
            for k, v := range r.Form {
                if len(k) > 31 && k[:31] == "household-relationships-answer-" {
                    answer_instance, _ := strconv.Atoi(k[31:])
                    answers[ak("household-relationships-answer", answer_instance, 0)] = v[0]
                }
            }
        } else {
            answers = parse_answers(r, 0)
        }

        update_answers(r, answers)

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
        answers := parse_answers(r, 0)
        update_answers(r, answers)

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
        var answers map[string]string
        if page == "date-of-birth" {
            answers = parse_date(r, "date-of-birth-answer", group_instance)
        } else {
            answers = parse_answers(r, group_instance)
        }

        update_answers(r, answers)

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
        answers := parse_answers(r, 0)
        update_answers(r, answers)
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
        var answers map[string]string
        if page == "date-of-birth" {
            answers = parse_date(r, "visitor-date-of-birth-answer", group_instance)
        } else {
            answers = parse_answers(r, group_instance)
        }

        update_answers(r, answers)

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
        answers := parse_answers(r, 0)
        update_answers(r, answers)
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
    user_id, _ := r.Cookie("user_id")
    answers := get_answers(user_id.Value, "mykey")
    flat_answers := []AnswerData{}

    for k, v := range answers {
        parts := strings.SplitN(k, ":", 3)
        answer_instance, _ := strconv.Atoi(parts[1])
        group_instance, _ := strconv.Atoi(parts[2])
        flat_answers = append(flat_answers, AnswerData{
            AnswerId: parts[0],
            AnswerInstance: answer_instance,
            GroupInstance: group_instance,
            Value: v,
        })
    }

    json.NewEncoder(w).Encode(flat_answers)
}

func handle_status(w http.ResponseWriter, r *http.Request) {
    fmt.Fprint(w, "OK")
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

func get_answers(user_id string, key string) map[string]string {
    if val, ok := storage[user_id]; ok {
        return val // TODO decrypt
    }
    return map[string]string{}
}

func put_answers(user_id string, answers map[string]string, key string) {
    storage[user_id] = answers // TODO encrypt
}

func update_answers(r *http.Request, new_answers map[string]string) map[string]string {
    user_id, _ := r.Cookie("user_id")
    storage_key := "mykey" // TODO
    answers := get_answers(user_id.Value, storage_key) // TODO get user from cookie

    for k, v := range new_answers {
        answers[k] = v
    }

    put_answers(user_id.Value, answers, storage_key)
    return answers
}

func ak(answer_id string, answer_instance int, group_instance int) string {
    return fmt.Sprintf("%v:%v:%v", answer_id, answer_instance, group_instance)
}

func parse_date(r *http.Request, answer_id string, group_instance int) map[string]string {
    r.ParseForm()
    year, _ := strconv.Atoi(r.Form[answer_id + "-year"][0])
    month, _ := strconv.Atoi(r.Form[answer_id + "-month"][0])
    day, _ := strconv.Atoi(r.Form[answer_id + "-day"][0])
    value := fmt.Sprintf("%04d-%02d-%02d", year, month, day)

    return map[string]string{ak(answer_id, 0, group_instance): value}
}

func parse_answers(r *http.Request, group_instance int) map[string]string {
    // TODO csrf
    r.ParseForm()

    var answers = map[string]string{}
    for k, vs := range r.Form {
        if k != "csrf_token" && k[:6] != "action" {
            // TODO ints and lists
            answers[ak(k, 0, group_instance)] = strings.Join(vs, ",")
        }
    }

    return answers
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
    http.HandleFunc("/status", handle_status)
    log.Fatal(http.ListenAndServe(":5001", nil))
}
