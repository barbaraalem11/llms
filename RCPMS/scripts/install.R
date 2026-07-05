repos <- getOption("repos")
if (is.null(repos) || repos["CRAN"] == "@CRAN@") {
  repos <- c(CRAN = "https://cloud.r-project.org")
}

install.packages("irace", repos = repos)